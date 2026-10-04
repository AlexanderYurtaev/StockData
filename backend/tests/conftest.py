import os

os.environ["FP_DATA_SOURCE"] = "demo"
os.environ["FP_CORS_ORIGINS"] = "http://localhost:5173"
# В тестах архив — in-memory, фоновая синхронизация выключена
os.environ["FP_DB_ENABLED"] = "1"
os.environ["FP_DB_PATH"] = ":memory:"
os.environ["FP_SYNC_INTERVAL"] = "0"
