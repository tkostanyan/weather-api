"""Database/Event Logger services package.

Provides abstract event logger interface and implementations for:
- MongoDB (local development)
- DynamoDB (AWS production)
"""

from app.services.database.dynamodb_logger import DynamoDBEventLogger
from app.services.database.memory_logger import InMemoryEventLogger
from app.services.database.mongodb_logger import MongoDBEventLogger

__all__ = ["MongoDBEventLogger", "DynamoDBEventLogger", "InMemoryEventLogger"]
