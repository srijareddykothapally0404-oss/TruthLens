import pandas as pd
import torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForSequenceClassification

BASE_DIR=Path(__file__).resolve().parent.parent
DATA_DIR=BASE_DIR/"data"
MODEL_DIR=BASE_DIR/"models"

MODEL_NAME="distilbert-base-uncased"
MAX_LENGTH=256

print("Loading data...")

train_df=pd.read_csv(DATA_DIR/"train.csv")
val_df=pd.read_csv(DATA_DIR/"validation.csv")

print("Train:",train_df.shape)
print("Validation:",val_df.shape)

print("\nLoading tokenizer...")

tokenizer=AutoTokenizer.from_pretrained(MODEL_NAME)

print("Tokenizer loaded")
print("Vocabulary size:",tokenizer.vocab_size)

print("\nTesting tokenization...")

sample=train_df["content"].iloc[0]

tokens=tokenizer(
    sample,
    truncation=True,
    padding="max_length",
    max_length=MAX_LENGTH
)

print("Original characters:",len(sample))
print("Token count:",len(tokens["input_ids"]))

print("\nLoading DistilBERT model...")

model=AutoModelForSequenceClassification.from_pretrained(
    MODEL_NAME,
    num_labels=2
)

device=torch.device("cuda" if torch.cuda.is_available() else "cpu")

print("Device:",device)

model=model.to(device)

print("Model loaded successfully!")
print("\nTruthLens DistilBERT setup is working.")