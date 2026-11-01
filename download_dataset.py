from datasets import load_dataset

def main():
    cache_dir = r"D:\2026_1\deep_learning\ocr-vietnamese\VietHTR-line"

    ds = load_dataset(
        "5CD-AI/VietHTR-Line",
        cache_dir=cache_dir,
    )

    print(ds)
    print(f"Dataset cache: {cache_dir}")

if __name__ == "__main__":
    main()