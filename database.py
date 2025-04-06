from datetime import datetime
import logging
from pymongo import MongoClient
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        """Initialize database connection."""
        try:
            # Connect to MongoDB
            self.client = MongoClient("mongodb+srv://krunalkanzariya:krunalkanzariya@primelinks.p0aov5y.mongodb.net/?retryWrites=true&w=majority&appName=primelinks")
            self.db = self.client.primelinks
            
            # Create collections
            self.users = self.db.users
            self.products = self.db.products
            self.categories = self.db.categories
            
            # Create indexes
            self.users.create_index("telegram_id", unique=True)
            self.products.create_index("title")
            self.categories.create_index("name", unique=True)
            
            logger.info("Successfully connected to MongoDB")
        except PyMongoError as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    def add_user(self, telegram_id: int, username: str, joined_date: datetime):
        """Add new user to database."""
        try:
            self.users.update_one(
                {"telegram_id": telegram_id},
                {
                    "$set": {
                        "username": username,
                        "joined_date": joined_date,
                        "last_active": datetime.now()
                    }
                },
                upsert=True
            )
            return True
        except PyMongoError as e:
            logger.error(f"Error adding user: {e}")
            return False

    def update_user_activity(self, telegram_id: int):
        """Update user's last active timestamp."""
        try:
            self.users.update_one(
                {"telegram_id": telegram_id},
                {"$set": {"last_active": datetime.now()}}
            )
            return True
        except PyMongoError as e:
            logger.error(f"Error updating user activity: {e}")
            return False

    def add_product(self, product_data: dict, category: str):
        """Add new product to database."""
        try:
            # Add category if it doesn't exist
            self.categories.update_one(
                {"name": category},
                {"$set": {"name": category}},
                upsert=True
            )
            
            # Add product with category reference
            product_data['category'] = category
            product_data['added_date'] = datetime.now()
            product_data['last_updated'] = datetime.now()
            
            result = self.products.insert_one(product_data)
            return str(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"Error adding product: {e}")
            return None

    def get_products_by_category(self, category: str):
        """Get all products in a category."""
        try:
            return list(self.products.find({"category": category}))
        except PyMongoError as e:
            logger.error(f"Error getting products by category: {e}")
            return []

    def get_all_products(self):
        """Get all products."""
        try:
            return list(self.products.find())
        except PyMongoError as e:
            logger.error(f"Error getting all products: {e}")
            return []

    def get_all_categories(self):
        """Get all categories."""
        try:
            return [cat['name'] for cat in self.categories.find()]
        except PyMongoError as e:
            logger.error(f"Error getting categories: {e}")
            return []

    def remove_product(self, product_id: str):
        """Remove a product by its ID."""
        try:
            result = self.products.delete_one({"_id": product_id})
            return result.deleted_count > 0
        except PyMongoError as e:
            logger.error(f"Error removing product: {e}")
            return False

    def update_product(self, product_id: str, product_data: dict):
        """Update product information."""
        try:
            product_data['last_updated'] = datetime.now()
            result = self.products.update_one(
                {"_id": product_id},
                {"$set": product_data}
            )
            return result.modified_count > 0
        except PyMongoError as e:
            logger.error(f"Error updating product: {e}")
            return False

    def get_user_stats(self):
        """Get user statistics."""
        try:
            total_users = self.users.count_documents({})
            active_today = self.users.count_documents({
                "last_active": {"$gte": datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)}
            })
            return {
                "total_users": total_users,
                "active_today": active_today
            }
        except PyMongoError as e:
            logger.error(f"Error getting user stats: {e}")
            return {"total_users": 0, "active_today": 0}

    def close(self):
        """Close database connection."""
        try:
            self.client.close()
        except PyMongoError as e:
            logger.error(f"Error closing database connection: {e}") 