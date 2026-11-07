import pandas as pd
import re
from pathlib import Path

BASE_DIR=Path(__file__).resolve().parent.parent
DATA_DIR=BASE_DIR/"data"

print("Loading datasets...")

fake=pd.read_csv(DATA_DIR/"Fake.csv")
true=pd.read_csv(DATA_DIR/"True.csv")

fake["label"]=0
true["label"]=1

df=pd.concat([fake,true],ignore_index=True)

print("Original dataset:",df.shape)

df["title"]=df["title"].fillna("")
df["text"]=df["text"].fillna("")

df["content"]=(df["title"]+" "+df["text"]).str.strip()

df=df[df["content"].str.len()>=50].copy()

before=len(df)

df=df.drop_duplicates(subset=["content"])

after=len(df)

print("Duplicates removed:",before-after)
print("After duplicate removal:",df.shape)

patterns=[
    r"Reuters",
    r"featured image",
    r"image via",
    r"Getty Images",
    r"21st Century Wire"
]

pattern="|".join(patterns)

df["content"]=df["content"].str.replace(
    pattern,
    "",
    regex=True
)

df["content"]=df["content"].str.replace(
    r"\s+",
    " ",
    regex=True
).str.strip()

df=df[df["content"].str.len()>=50].copy()

output=DATA_DIR/"cleaned_data.csv"

df[["content","label"]].to_csv(output,index=False)

print("Final dataset:",df.shape)
print("Fake:",(df["label"]==0).sum())
print("Real:",(df["label"]==1).sum())
print("Saved to:",output)