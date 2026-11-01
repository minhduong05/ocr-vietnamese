from pathlib import Path
from datasets import Dataset, DatasetDict, concatenate_datasets
import shutil

root = Path("VietHTR-line")

train_files = sorted(root.rglob("*-train-*.arrow"))
test_file = next(root.rglob("*-test.arrow"))

ds = DatasetDict({
    "train": concatenate_datasets([
        Dataset.from_file(str(path)) for path in train_files
    ]),
    "test": Dataset.from_file(str(test_file)),
})

ds.save_to_disk("data/viet_htr")
shutil.make_archive("viet_htr", "zip", "data", "viet_htr")

print("Đã tạo viet_htr.zip")