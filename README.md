# FastAPI Practice

Project thực hành FastAPI theo từng ngày và quản lý thay đổi bằng GitHub Pull Request.

## Environment

- Windows
- Conda
- Python 3.11
- FastAPI

## Create environment

```bat
conda env create -f environment.yml
conda activate fastapi_practice
```

## Run application

```bat
python -m uvicorn app.main:app --reload
```

## API documentation

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health check: http://127.0.0.1:8000/api/v1/health

## Run tests

```bat
pytest -v
```

## Check code

```bat
ruff check .
ruff format --check .
```

## Format code

```bat
ruff format .
```