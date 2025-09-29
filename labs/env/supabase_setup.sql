create extension if not exists vector;

create table if not exists documents (
  id bigserial primary key,
  source text,
  chunk text,
  embedding vector(1536)
);

-- Vector index for cosine similarity via ivfflat
do $$
begin
  create index if not exists documents_embedding_ivfflat
  on documents using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);
exception when others then null; -- ignore errors if extension/index ops differ by version
end $$;

