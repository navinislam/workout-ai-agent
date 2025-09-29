import os
from dotenv import load_dotenv
from pymilvus import (
    connections,
    FieldSchema, CollectionSchema, DataType, Collection
)


COLLECTION_NAME = "docs"
DIM = 1536


def ensure_collection():
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=DIM),
    ]
    schema = CollectionSchema(fields, description="RAG documents")
    col = Collection(COLLECTION_NAME, schema)

    # Create index if not exists
    try:
        col.create_index(
            field_name="vector",
            index_params={
                "index_type": "IVF_FLAT",
                "metric_type": "COSINE",
                "params": {"nlist": 1024},
            },
        )
    except Exception as e:
        # index may already exist
        print("Index create skipped:", e)
    col.load()
    return col


def main():
    load_dotenv()
    host = os.getenv("MILVUS_HOST", "localhost")
    port = os.getenv("MILVUS_PORT", "19530")
    print(f"Connecting Milvus at {host}:{port} ...")
    connections.connect(alias="default", host=host, port=port)
    col = ensure_collection()
    print(f"Collection ready: {col.name}")


if __name__ == "__main__":
    main()

