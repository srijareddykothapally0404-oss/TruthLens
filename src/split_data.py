import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split

BASE_DIR=Path(__file__).resolve().parent.parent
DATA_DIR=BASE_DIR/"data"

print("Loading cleaned dataset...")

df=pd.read_csv(DATA_DIR/"cleaned_data.csv")

print("Dataset:",df.shape)
print("Fake:",(df["label"]==0).sum())
print("Real:",(df["label"]==1).sum())

train_df,temp_df=train_test_split(
    df,
    test_size=0.30,
    random_state=42,
    stratify=df["label"]
)

val_df,test_df=train_test_split(
    temp_df,
    test_size=0.50,
    random_state=42,
    stratify=temp_df["label"]
)

print("\nSplit sizes:")
print("Train:",train_df.shape)
print("Validation:",val_df.shape)
print("Test:",test_df.shape)

print("\nLabel distribution:")

print("Train:")
print(train_df["label"].value_counts().sort_index())

print("\nValidation:")
print(val_df["label"].value_counts().sort_index())

print("\nTest:")
print(test_df["label"].value_counts().sort_index())

train_text=set(train_df["content"])
val_text=set(val_df["content"])
test_text=set(test_df["content"])

print("\nDuplicate overlap checks:")
print("Train ∩ Validation:",len(train_text & val_text))
print("Train ∩ Test:",len(train_text & test_text))
print("Validation ∩ Test:",len(val_text & test_text))

train_df.to_csv(DATA_DIR/"train.csv",index=False)
val_df.to_csv(DATA_DIR/"validation.csv",index=False)
test_df.to_csv(DATA_DIR/"test.csv",index=False)

print("\nSaved:")
print(DATA_DIR/"train.csv")
print(DATA_DIR/"validation.csv")
print(DATA_DIR/"test.csv")