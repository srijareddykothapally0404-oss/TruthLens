"""Safe, lightweight extraction of text from common news input formats with Trafilatura and OCR preprocessing."""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from collections.abc import Callable, Iterable
from io import BytesIO
from pathlib import PurePath
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpcore
import httpx

LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 8.0
DEFAULT_MAX_RESPONSE_BYTES = 2_000_000
DEFAULT_MAX_INPUT_LENGTH = 100_000
DEFAULT_MAX_UPLOAD_BYTES = 8_000_000
DEFAULT_MAX_IMAGE_PIXELS = 20_000_000
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_USER_AGENT = "TruthLensAI/1.0 (public article text extraction)"
DEFAULT_OCR_TIMEOUT_SECONDS = 15
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
_IMAGE_SIGNATURES = {
    ".png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    ".jpg": lambda data: data.startswith(b"\xff\xd8\xff"),
    ".jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    ".webp": lambda data: (
        len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    ),
}
_SOCIAL_DOMAINS = {"x.com", "twitter.com", "facebook.com", "www.facebook.com"}
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}

# Try to import Trafilatura
try:
    import trafilatura
    from trafilatura.settings import use_config
    TRAFILATURA_AVAILABLE = True
    # Configure Trafilatura for better extraction
    TRAFILATURA_CONFIG = use_config()
    TRAFILATURA_CONFIG.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")
    TRAFILATURA_CONFIG.set("DEFAULT", "MIN_EXTRACTED_SIZE", "100")
    TRAFILATURA_CONFIG.set("DEFAULT", "MIN_OUTPUT_SIZE", "50")
except ImportError:
    TRAFILATURA_AVAILABLE = False
    trafilatura = None
    TRAFILATURA_CONFIG = None


class URLRejectedError(ValueError):
    """Raised when a URL is malformed or points to a non-public destination."""


class ResponseTooLargeError(ValueError):
    """Raised when an external page exceeds the configured response limit."""


class _PinnedNetworkBackend(httpcore.SyncBackend):
    def __init__(
        self,
        hostname: str,
        addresses: tuple[str, ...],
    ) -> None:
        self.hostname = hostname.casefold()
        self.addresses = addresses
        self._delegate = httpcore.SyncBackend()

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> Any:
        if host.casefold() != self.hostname:
            return self._delegate.connect_tcp(
                host,
                port,
                timeout,
                local_address,
                socket_options,
            )
        last_error: Exception | None = None
        for address in self.addresses:
            try:
                # HTTP core retains the original hostname for Host and TLS SNI.
                return self._delegate.connect_tcp(
                    address,
                    port,
                    timeout,
                    local_address,
                    socket_options,
                )
            except (OSError, httpcore.ConnectError) as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise OSError("No validated address is available for this host.")

    def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> Any:
        return self._delegate.connect_unix_socket(path, timeout, socket_options)

    def sleep(self, seconds: float) -> None:
        self._delegate.sleep(seconds)


# Fallback HTML parser (kept for when Trafilatura is unavailable)
class _ArticleParser:
    """Fallback HTML parser when Trafilatura is unavailable."""

    _SKIP_TAGS = {
        "aside", "button", "footer", "form", "nav", "noscript",
        "script", "style", "svg",
    }
    _VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img",
        "input", "link", "meta", "param", "source", "track", "wbr",
    }
    _NON_ARTICLE_PATTERN = re.compile(
        r"(?:^|[\s_-])(?:ad|ads|advertisement|advertising|related|"
        r"recommendations?|recommended|trending|popular|newsletter|comments?|"
        r"social|share|breadcrumbs?|sidebar|navigation|nav|footer|"
        r"promoted|sponsored|widgets?|recirculation|most-read|more-stories)"
        r"(?:$|[\s_-])",
        re.IGNORECASE,
    )
    _ARTICLE_CONTAINER_PATTERN = re.compile(
        r"(?:^|[\s_-])(?:article|story|post)[\s_-]?(?:body|content)"
        r"(?:$|[\s_-])",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        from html.parser import HTMLParser

        self.parser = HTMLParser(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.headline_parts: list[str] = []
        self.paragraphs: list[str] = []
        self.article_paragraphs: list[str] = []
        self.main_parts: list[str] = []
        self._title_depth = 0
        self._headline_depth = 0
        self._headline_found = False
        self._paragraph_depth = 0
        self._paragraph_parts: list[str] = []
        self._main_depth = 0
        self._main_tags: list[str] = []
        self._skip_depth = 0

        # Bind handler methods
        self.parser.handle_starttag = self._handle_starttag
        self.parser.handle_endtag = self._handle_endtag
        self.parser.handle_data = self._handle_data

    def _handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        attributes = {key.casefold(): value for key, value in attrs}
        if self._skip_depth:
            if tag not in self._VOID_TAGS:
                self._skip_depth += 1
            return
        if tag in self._SKIP_TAGS or "hidden" in attributes or str(
            attributes.get("aria-hidden") or ""
        ).casefold() == "true":
            if tag not in self._VOID_TAGS:
                self._skip_depth = 1
            return
        metadata = " ".join(
            str(attributes.get(name) or "")
            for name in ("class", "id", "role", "aria-label", "data-testid")
        )
        if self._NON_ARTICLE_PATTERN.search(metadata):
            if tag not in self._VOID_TAGS:
                self._skip_depth = 1
            return
        if tag == "title":
            self._title_depth += 1
        if tag == "h1" and not self._headline_found:
            self._headline_depth += 1
            self._headline_found = True
        if (
            tag in {"article", "main"}
            or "article" in (attributes.get("role") or "").casefold().split()
            or "main" in (attributes.get("role") or "").casefold().split()
            or (attributes.get("itemprop") or "").casefold() == "articlebody"
            or self._ARTICLE_CONTAINER_PATTERN.search(metadata)
        ):
            self._main_depth += 1
            self._main_tags.append(tag)
        if tag == "p":
            if not self._paragraph_depth:
                self._paragraph_parts = []
            self._paragraph_depth += 1

    def _handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "title" and self._title_depth:
            self._title_depth -= 1
        if tag == "h1" and self._headline_depth:
            self._headline_depth -= 1
        if tag in self._main_tags:
            self._main_tags.remove(tag)
            self._main_depth -= 1
        if tag == "p" and self._paragraph_depth:
            self._paragraph_depth -= 1
            if not self._paragraph_depth:
                text = " ".join(" ".join(self._paragraph_parts).split())
                if text:
                    self.paragraphs.append(text)
                    if self._main_depth:
                        self.article_paragraphs.append(text)
                self._paragraph_parts = []

    def _handle_data(self, data: str) -> None:
        if self._skip_depth or not data.strip():
            return
        if self._title_depth:
            self.title_parts.append(data)
        if self._headline_depth:
            self.headline_parts.append(data)
        if self._paragraph_depth:
            self._paragraph_parts.append(data)
        if self._main_depth and not self._headline_depth:
            self.main_parts.append(data)

    def feed(self, document: str) -> None:
        self.parser.feed(document)

    def close(self) -> None:
        self.parser.close()

    def result(self) -> tuple[str | None, str]:
        title = (
            " ".join(" ".join(self.headline_parts).split())
            or " ".join(" ".join(self.title_parts).split())
            or None
        )
        paragraphs: list[str] = []
        seen: set[str] = set()
        candidates = self.article_paragraphs or self.paragraphs
        for paragraph in candidates:
            key = paragraph.casefold()
            if key not in seen:
                seen.add(key)
                paragraphs.append(paragraph)
        body = "\n\n".join(paragraphs)
        if not body and self.main_parts:
            body = " ".join(" ".join(self.main_parts).split())
        return title, body


def _result(
    *,
    input_type: str,
    original_input: str,
    extracted_text: str = "",
    source_url: str | None = None,
    processing_status: str,
    warnings: Iterable[str] = (),
    error: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    return {
        "input_type": input_type,
        "original_input": original_input,
        "extracted_text": extracted_text,
        "source_url": source_url,
        "processing_status": processing_status,
        "warnings": list(warnings),
        "error": error,
        "title": title,
    }


def _preprocess_image_for_ocr(image: Any) -> Any:
    """Preprocess image for better OCR: grayscale, resize, denoise, deskew."""
    try:
        from PIL import Image, ImageFilter, ImageOps
        import numpy as np

        # Convert to grayscale
        if image.mode != 'L':
            image = image.convert('L')

        # Resize if too small (scale up 2x for better OCR)
        min_dimension = 600
        if image.width < min_dimension or image.height < min_dimension:
            scale = max(min_dimension / image.width, min_dimension / image.height)
            new_size = (int(image.width * scale), int(image.height * scale))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        # Denoise: apply median filter
        image = image.filter(ImageFilter.MedianFilter(size=3))

        # Deskew: detect and correct rotation
        # Convert to numpy for skew detection
        img_array = np.array(image)
        if img_array.size > 0:
            # Simple deskew using Hough transform or projection profile
            # For now, apply basic contrast enhancement
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.0)

        return image
    except Exception:
        # Return original if preprocessing fails
        LOGGER.exception("Image preprocessing failed, using original")
        return image


class InputProcessor:
    """Convert text, public article pages, and screenshots to clean text."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        max_input_length: int = DEFAULT_MAX_INPUT_LENGTH,
        max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
        max_image_pixels: int = DEFAULT_MAX_IMAGE_PIXELS,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        user_agent: str = DEFAULT_USER_AGENT,
        ocr_timeout: int = DEFAULT_OCR_TIMEOUT_SECONDS,
        dns_resolver: Callable[..., list[tuple[Any, ...]]] | None = None,
        transport: httpx.BaseTransport | None = None,
        ocr_engine: Callable[[Any], str] | None = None,
        ocr_preprocess: bool = True,
        trafilatura_enabled: bool = True,
    ) -> None:
        if timeout <= 0 or ocr_timeout <= 0:
            raise ValueError("timeouts must be positive.")
        if min(
            max_response_bytes,
            max_input_length,
            max_upload_bytes,
            max_image_pixels,
        ) <= 0:
            raise ValueError("input and response limits must be positive.")
        if max_redirects < 0:
            raise ValueError("max_redirects cannot be negative.")
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.max_input_length = max_input_length
        self.max_upload_bytes = max_upload_bytes
        self.max_image_pixels = max_image_pixels
        self.max_redirects = max_redirects
        self.user_agent = user_agent
        self.ocr_timeout = ocr_timeout
        self.dns_resolver = dns_resolver or socket.getaddrinfo
        self.transport = transport
        self.ocr_engine = ocr_engine
        self.ocr_preprocess = ocr_preprocess
        self.trafilatura_enabled = trafilatura_enabled and TRAFILATURA_AVAILABLE

    def process(
        self,
        value: str,
        input_type: str = "auto",
    ) -> dict[str, Any]:
        if not isinstance(value, str):
            raise TypeError("Input must be a string.")
        if input_type not in {"auto", "text", "url", "forwarded"}:
            raise ValueError("input_type must be auto, text, url, or forwarded.")
        if input_type == "url" or (
            input_type == "auto" and self._looks_like_url(value)
        ):
            return self.process_url(value)
        return self.process_text(value, forwarded=input_type == "forwarded")

    def process_text(
        self,
        text: str,
        *,
        forwarded: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(text, str):
            raise TypeError("Text input must be a string.")
        input_type = "forwarded_text" if forwarded or self._looks_forwarded(text) else "text"
        original = text
        normalized = text.strip()
        if not normalized:
            return _result(
                input_type=input_type,
                original_input=original,
                processing_status="rejected",
                error="Text must not be empty or whitespace.",
            )
        if len(normalized) > self.max_input_length:
            return _result(
                input_type=input_type,
                original_input=original,
                processing_status="rejected",
                error=f"Text exceeds the maximum length of {self.max_input_length} characters.",
            )
        warnings = (
            ["Forwarded text is user-submitted and has not been independently verified."]
            if input_type == "forwarded_text"
            else []
        )
        return _result(
            input_type=input_type,
            original_input=original,
            extracted_text=normalized,
            processing_status="processed",
            warnings=warnings,
        )

    def process_url(self, url: str) -> dict[str, Any]:
        if not isinstance(url, str):
            raise TypeError("URL input must be a string.")
        original = url
        try:
            host = (urlsplit(url.strip()).hostname or "").casefold().rstrip(".")
        except ValueError:
            host = ""
        social_url = any(
            host == domain or host.endswith(f".{domain}")
            for domain in _SOCIAL_DOMAINS
        )
        input_type = "social_url" if social_url else "article_url"
        try:
            self._validate_public_url(url)
        except URLRejectedError as exc:
            return _result(
                input_type=input_type,
                original_input=original,
                source_url=original,
                processing_status="rejected",
                error=str(exc),
            )
        except OSError:
            return self._unavailable_url(
                original,
                input_type,
                "The URL host could not be resolved.",
            )

        try:
            html, final_url, content_type = self._fetch_page(url)
        except URLRejectedError as exc:
            return _result(
                input_type=input_type,
                original_input=original,
                source_url=original,
                processing_status="rejected",
                error=str(exc),
            )
        except ResponseTooLargeError as exc:
            return _result(
                input_type=input_type,
                original_input=original,
                source_url=original,
                processing_status="rejected",
                error=str(exc),
            )
        except httpx.TimeoutException:
            return self._unavailable_url(original, input_type, "The page request timed out.")
        except httpx.HTTPStatusError as exc:
            if social_url and exc.response.status_code in {401, 403, 404, 429}:
                return _result(
                    input_type=input_type,
                    original_input=original,
                    source_url=original,
                    processing_status="unsupported",
                    warnings=["The social media post is not directly accessible without authentication."],
                    error="Post content was not publicly accessible.",
                )
            return self._unavailable_url(
                original,
                input_type,
                f"The page returned HTTP {exc.response.status_code}.",
            )
        except (httpx.RequestError, OSError):
            return self._unavailable_url(
                original,
                input_type,
                "The page could not be reached.",
            )
        except Exception:
            LOGGER.exception("Unexpected external page processing error")
            return self._unavailable_url(
                original,
                input_type,
                "The page could not be processed.",
            )

        if content_type not in {"text/html", "application/xhtml+xml"}:
            return _result(
                input_type=input_type,
                original_input=original,
                source_url=final_url,
                processing_status="unsupported",
                error="The URL did not return an HTML page.",
            )

        # Try Trafilatura first if enabled
        extracted_text = ""
        title = None
        warnings = []

        if self.trafilatura_enabled:
            try:
                # Use Trafilatura for extraction
                extracted = trafilatura.extract(
                    html,
                    config=TRAFILATURA_CONFIG,
                    include_comments=False,
                    include_tables=False,
                    include_images=False,
                    no_fallback=False,
                    favor_recall=True,
                    with_metadata=True,
                    output_format="json",
                )
                if extracted:
                    import json
                    metadata = json.loads(extracted)
                    extracted_text = metadata.get("text", "")
                    title = metadata.get("title") or None
                    if extracted_text and len(extracted_text) >= 50:
                        warnings.append(
                            "Text extracted using Trafilatura (best-effort, may miss content)."
                        )
                    else:
                        extracted_text = ""
            except Exception:
                LOGGER.warning("Trafilatura extraction failed, falling back to custom parser")
                extracted_text = ""

        # Fallback to custom parser if Trafilatura failed or not enabled
        if not extracted_text or len(extracted_text) < 50:
            try:
                document = html.decode("utf-8", errors="replace")
                parser = _ArticleParser()
                parser.feed(document)
                parser.close()
                fallback_title, fallback_body = parser.result()
                if not title:
                    title = fallback_title
                if fallback_body and len(fallback_body) > len(extracted_text):
                    extracted_text = fallback_body
                    warnings.append(
                        "Fallback parser used; only static page text was extracted."
                    )
            except Exception:
                LOGGER.exception("HTML parsing failed")
                return _result(
                    input_type=input_type,
                    original_input=original,
                    source_url=final_url,
                    processing_status="failed",
                    error="The page HTML could not be parsed.",
                )

        if len(extracted_text) < 50:
            if social_url:
                return _result(
                    input_type=input_type,
                    original_input=original,
                    source_url=final_url,
                    processing_status="unsupported",
                    warnings=["JavaScript-rendered or restricted post content is not fetched."],
                    error="No directly accessible post text was found.",
                    title=title,
                )
            return _result(
                input_type=input_type,
                original_input=original,
                source_url=final_url,
                processing_status="unsupported",
                warnings=["Page title and metadata are not treated as article text."],
                error="No readable article body was found.",
                title=title,
            )
        if len(extracted_text) > self.max_input_length:
            return _result(
                input_type=input_type,
                original_input=original,
                source_url=final_url,
                processing_status="rejected",
                error=f"Extracted text exceeds the maximum length of {self.max_input_length} characters.",
                title=title,
            )

        final_text = f"{title}\n\n{extracted_text}" if title else extracted_text
        return _result(
            input_type=input_type,
            original_input=original,
            extracted_text=final_text,
            source_url=final_url,
            processing_status="processed",
            warnings=warnings,
            title=title,
        )

    def process_image(self, image_bytes: bytes, filename: str) -> dict[str, Any]:
        safe_filename = PurePath(filename or "uploaded-image").name
        if not isinstance(image_bytes, bytes):
            raise TypeError("Image upload must be bytes.")
        extension = PurePath(safe_filename).suffix.casefold()
        if extension not in SUPPORTED_IMAGE_EXTENSIONS:
            return _result(
                input_type="image",
                original_input=safe_filename,
                processing_status="unsupported",
                error="Only PNG, JPG/JPEG, and WEBP images are supported.",
            )
        if len(image_bytes) > self.max_upload_bytes:
            return _result(
                input_type="image",
                original_input=safe_filename,
                processing_status="rejected",
                error=f"Image exceeds the maximum upload size of {self.max_upload_bytes} bytes.",
            )
        if not image_bytes or not _IMAGE_SIGNATURES[extension](image_bytes):
            return _result(
                input_type="image",
                original_input=safe_filename,
                processing_status="rejected",
                error="The file content does not not match a supported image format.",
            )
        try:
            from PIL import Image, UnidentifiedImageError

            with Image.open(BytesIO(image_bytes)) as image:
                expected_format = {
                    ".png": "PNG",
                    ".jpg": "JPEG",
                    ".jpeg": "JPEG",
                    ".webp": "WEBP",
                }[extension]
                if image.format != expected_format:
                    raise ValueError("The file extension does not match its image format.")
                if image.width * image.height > self.max_image_pixels:
                    return _result(
                        input_type="image",
                        original_input=safe_filename,
                        processing_status="rejected",
                        error=f"Image dimensions exceed the maximum of {self.max_image_pixels} pixels.",
                    )
                image.verify()
            with Image.open(BytesIO(image_bytes)) as image:
                image.load()
                try:
                    text = self._run_ocr(image)
                except ModuleNotFoundError:
                    return _result(
                        input_type="image",
                        original_input=safe_filename,
                        processing_status="unavailable",
                        warnings=["Install the optional OCR dependencies and Tesseract executable to enable image text extraction."],
                        error="Local OCR is not installed.",
                    )
                except Exception as exc:
                    if self._is_ocr_unavailable(exc):
                        return _result(
                            input_type="image",
                            original_input=safe_filename,
                            processing_status="unavailable",
                            warnings=["Install the optional Tesseract OCR executable to enable image text extraction."],
                            error="The local OCR engine is unavailable.",
                        )
                    LOGGER.exception("OCR failed")
                    return _result(
                        input_type="image",
                        original_input=safe_filename,
                        processing_status="failed",
                        error="Text could not be extracted from the image.",
                    )
        except ModuleNotFoundError:
            return _result(
                input_type="image",
                original_input=safe_filename,
                processing_status="unavailable",
                warnings=["Install the optional Pillow and pytesseract packages and Tesseract executable to enable image text extraction."],
                error="Image processing dependencies are not installed.",
            )
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            return _result(
                input_type="image",
                original_input=safe_filename,
                processing_status="rejected",
                error=str(exc) or "The image is corrupted or unsupported.",
            )
        except Exception:
            LOGGER.exception("Image validation failed")
            return _result(
                input_type="image",
                original_input=safe_filename,
                processing_status="rejected",
                error="The image is corrupted or could not be decoded.",
            )

        if not isinstance(text, str):
            return _result(
                input_type="image",
                original_input=safe_filename,
                processing_status="failed",
                error="The OCR engine returned an invalid result.",
            )
        normalized = " ".join(text.split())
        if not any(character.isalnum() for character in normalized):
            return _result(
                input_type="image",
                original_input=safe_filename,
                processing_status="no_text",
                warnings=["OCR did not find usable text in the image."],
            )
        if len(normalized) > self.max_input_length:
            return _result(
                input_type="image",
                original_input=safe_filename,
                processing_status="rejected",
                error=f"OCR text exceeds the maximum length of {self.max_input_length} characters.",
            )
        return _result(
            input_type="image",
            original_input=safe_filename,
            extracted_text=normalized,
            processing_status="processed",
        )

    def _run_ocr(self, image: Any) -> str:
        if self.ocr_engine is not None:
            return self.ocr_engine(image)

        # Preprocess image if enabled
        if self.ocr_preprocess:
            image = _preprocess_image_for_ocr(image)

        import pytesseract

        return pytesseract.image_to_string(image, timeout=self.ocr_timeout)

    @staticmethod
    def _is_ocr_unavailable(error: Exception) -> bool:
        return error.__class__.__name__ in {
            "TesseractNotFoundError",
            "TesseractNotFoundException",
        }

    @staticmethod
    def _looks_like_url(value: str) -> bool:
        candidate = value.strip()
        return candidate.casefold().startswith(("http://", "https://"))

    @staticmethod
    def _looks_forwarded(value: str) -> bool:
        lowered = value.casefold()
        return bool(
            re.search(
                r"(?im)^\s*forwarded(?:\s+many\s+times|\s+from\b.*)?\s*$",
                value,
            )
        ) or any(
            marker in lowered
            for marker in (
                "forwarded message",
                "forwarded many times",
                "----- forwarded",
                "begin forwarded message",
            )
        )

    def _validate_public_url(self, value: str):
        try:
            parsed = urlsplit(value.strip())
            scheme = parsed.scheme.casefold()
            host = (parsed.hostname or "").casefold().rstrip(".")
            port = parsed.port
        except ValueError as exc:
            raise URLRejectedError("The URL is malformed.") from exc
        if scheme not in {"http", "https"} or not host:
            raise URLRejectedError("Only absolute HTTP and HTTPS URLs are accepted.")
        if parsed.username is not None or parsed.password is not None:
            raise URLRejectedError("URLs containing user credentials are not allowed.")
        if port is not None and port != (443 if scheme == "https" else 80):
            raise URLRejectedError("Non-standard URL ports are not allowed.")
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise URLRejectedError("Local and internal network URLs are not allowed.")

        try:
            literal_ip = ipaddress.ip_address(host)
        except ValueError:
            literal_ip = None
        if literal_ip is not None:
            if not literal_ip.is_global:
                raise URLRejectedError("Private and non-public IP addresses are not allowed.")
            addresses = [literal_ip]
        else:
            try:
                resolved = self.dns_resolver(
                    host,
                    port or (443 if scheme == "https" else 80),
                    type=socket.SOCK_STREAM,
                )
            except OSError as exc:
                raise OSError("The URL host could not be resolved.") from exc
            addresses = []
            for record in resolved:
                try:
                    addresses.append(ipaddress.ip_address(record[4][0]))
                except (IndexError, ValueError, TypeError):
                    continue
        if not addresses:
            raise OSError("The URL host did not resolve to an address.")
        if any(not address.is_global for address in addresses):
            raise URLRejectedError("The URL resolves to a private or non-public IP address.")
        return parsed, tuple(dict.fromkeys(str(address) for address in addresses))

    def _fetch_page(self, url: str) -> tuple[bytes, str, str]:
        current_url = url.strip()
        for redirect_count in range(self.max_redirects + 1):
            parsed, addresses = self._validate_public_url(current_url)
            transport = self.transport
            if transport is None:
                transport = httpx.HTTPTransport(trust_env=False)
                hostname = (parsed.hostname or "").encode("idna").decode("ascii")
                transport._pool._network_backend = _PinnedNetworkBackend(
                    hostname,
                    addresses,
                )
            with httpx.Client(
                timeout=httpx.Timeout(self.timeout),
                headers={"User-Agent": self.user_agent},
                follow_redirects=False,
                trust_env=False,
                transport=transport,
            ) as client:
                with client.stream("GET", current_url) as response:
                    if response.status_code in _REDIRECT_STATUSES:
                        if redirect_count >= self.max_redirects:
                            raise URLRejectedError("The page exceeded the redirect limit.")
                        location = response.headers.get("location")
                        if not location:
                            raise URLRejectedError("The page returned an invalid redirect.")
                        current_url = urljoin(current_url, location)
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get(
                        "content-type", ""
                    ).split(";", 1)[0].strip().casefold()
                    if content_type not in {"text/html", "application/xhtml+xml"}:
                        return b"", str(response.url), content_type
                    content_length = response.headers.get("content-length")
                    if content_length:
                        try:
                            declared_size = int(content_length)
                        except ValueError:
                            declared_size = 0
                        if declared_size > self.max_response_bytes:
                            raise ResponseTooLargeError(
                                "The page exceeds the maximum response size."
                            )
                    chunks: list[bytes] = []
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > self.max_response_bytes:
                            raise ResponseTooLargeError(
                                "The page exceeds the maximum response size."
                            )
                        chunks.append(chunk)
                    return b"".join(chunks), str(response.url), content_type
        raise URLRejectedError("The page exceeded the redirect limit.")

    @staticmethod
    def _unavailable_url(
        original: str,
        input_type: str,
        message: str,
    ) -> dict[str, Any]:
        return _result(
            input_type=input_type,
            original_input=original,
            source_url=original,
            processing_status="unavailable",
            error=message,
        )