import pandas as pd
import torch
from torch.utils.data import Dataset,DataLoader
from transformers import AutoTokenizer,AutoModelForSequenceClassification
from pathlib import Path
from tqdm import tqdm

BASE_DIR=Path(__file__).resolve().parent.parent
DATA_DIR=BASE_DIR/"data"
MODEL_DIR=BASE_DIR/"models"

MODEL_NAME="distilbert-base-uncased"
MAX_LENGTH=256
BATCH_SIZE=4
LEARNING_RATE=2e-5
EPOCHS=3

CHECKPOINT=MODEL_DIR/"latest_checkpoint.pt"

device=torch.device("cuda" if torch.cuda.is_available() else "cpu")

print("Device:",device)

train_df=pd.read_csv(DATA_DIR/"train.csv")
val_df=pd.read_csv(DATA_DIR/"validation.csv")

print("Train:",train_df.shape)
print("Validation:",val_df.shape)

tokenizer=AutoTokenizer.from_pretrained(MODEL_NAME)

class NewsDataset(Dataset):
    def __init__(self,df):
        self.texts=df["content"].tolist()
        self.labels=df["label"].tolist()

    def __len__(self):
        return len(self.texts)

    def __getitem__(self,index):
        encoding=tokenizer(
            self.texts[index],
            truncation=True,
            padding="max_length",
            max_length=MAX_LENGTH,
            return_tensors="pt"
        )

        item={
            "input_ids":encoding["input_ids"].squeeze(0),
            "attention_mask":encoding["attention_mask"].squeeze(0),
            "labels":torch.tensor(self.labels[index],dtype=torch.long)
        }

        return item

train_dataset=NewsDataset(train_df)
val_dataset=NewsDataset(val_df)

train_loader=DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True
)

val_loader=DataLoader(
    val_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False
)

print("Train batches:",len(train_loader))
print("Validation batches:",len(val_loader))

model=AutoModelForSequenceClassification.from_pretrained(
    MODEL_NAME,
    num_labels=2
)

model=model.to(device)

optimizer=torch.optim.AdamW(
    model.parameters(),
    lr=LEARNING_RATE
)

start_epoch=0
best_val_accuracy=0.0

if CHECKPOINT.exists():
    print("\nCheckpoint found!")
    print("Loading checkpoint...")

    checkpoint=torch.load(
        CHECKPOINT,
        map_location=device
    )

    model.load_state_dict(checkpoint["model_state_dict"])
    optimizer.load_state_dict(checkpoint["optimizer_state_dict"])

    start_epoch=checkpoint["epoch"]+1
    best_val_accuracy=checkpoint["best_val_accuracy"]

    print("Resuming from epoch:",start_epoch+1)
    print("Best validation accuracy:",best_val_accuracy)

else:
    print("\nNo checkpoint found.")
    print("Starting training from the beginning.")

for epoch in range(start_epoch,EPOCHS):

    print("\n==============================")
    print("Epoch",epoch+1,"/",EPOCHS)
    print("==============================")

    model.train()

    total_loss=0
    correct=0
    total=0

    progress=tqdm(
        train_loader,
        desc="Training"
    )

    for batch in progress:

        input_ids=batch["input_ids"].to(device)
        attention_mask=batch["attention_mask"].to(device)
        labels=batch["labels"].to(device)

        optimizer.zero_grad()

        outputs=model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels
        )

        loss=outputs.loss
        logits=outputs.logits

        loss.backward()
        optimizer.step()

        total_loss+=loss.item()

        predictions=torch.argmax(logits,dim=1)

        correct+=(predictions==labels).sum().item()
        total+=labels.size(0)

        progress.set_postfix(
            loss=loss.item(),
            accuracy=correct/total
        )

    train_loss=total_loss/len(train_loader)
    train_accuracy=correct/total

    print("\nTrain Loss:",train_loss)
    print("Train Accuracy:",train_accuracy)

    model.eval()

    val_correct=0
    val_total=0

    with torch.no_grad():

        for batch in tqdm(
            val_loader,
            desc="Validation"
        ):

            input_ids=batch["input_ids"].to(device)
            attention_mask=batch["attention_mask"].to(device)
            labels=batch["labels"].to(device)

            outputs=model(
                input_ids=input_ids,
                attention_mask=attention_mask
            )

            predictions=torch.argmax(
                outputs.logits,
                dim=1
            )

            val_correct+=(predictions==labels).sum().item()
            val_total+=labels.size(0)

    val_accuracy=val_correct/val_total

    print("\nValidation Accuracy:",val_accuracy)

    if val_accuracy>best_val_accuracy:
        best_val_accuracy=val_accuracy

        torch.save(
            model.state_dict(),
            MODEL_DIR/"best_model.pt"
        )

        print("Best model saved!")

    torch.save(
        {
            "epoch":epoch,
            "model_state_dict":model.state_dict(),
            "optimizer_state_dict":optimizer.state_dict(),
            "best_val_accuracy":best_val_accuracy
        },
        CHECKPOINT
    )

    print("Checkpoint saved!")

print("\nTraining finished.")
print("Best Validation Accuracy:",best_val_accuracy)