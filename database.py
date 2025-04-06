from datetime import datetime
import logging
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import os

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        """Initialize database connection."""
        try:
            self.client = MongoClient(os.getenv('MONGODB_URI'))
            self.db = self.client[os.getenv('DB_NAME', 'amazon_deals_bot')]
            self.users = self.db.users
            self.products = self.db.products
            self.categories = self.db.categories  # New collection for categories
            
            # Create indexes
            self.users.create_index("telegram_id", unique=True)
            self.products.create_index("title")
            self.categories.create_index("name", unique=True)
            
            logger.info("Connected to MongoDB successfully")
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {e}")
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

    def add_category(self, category_name):
        """Add a new category to the database."""
        try:
            # Check if category already exists
            if self.categories.find_one({'name': category_name}):
                return False
            
            # Add new category
            result = self.categories.insert_one({
                'name': category_name,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            })
            
            return bool(result.inserted_id)
        except Exception as e:
            logger.error(f"Error adding category: {e}")
            return False

    def remove_category(self, category_name):
        """Remove a category and all its products from the database."""
        try:
            # Start a session for atomic operation
            with self.client.start_session() as session:
                with session.start_transaction():
                    # First, remove all products in this category
                    delete_products_result = self.products.delete_many(
                        {'category': category_name},
                        session=session
                    )
                    
                    # Then remove the category
                    delete_category_result = self.categories.delete_one(
                        {'name': category_name},
                        session=session
                    )
                    
                    if delete_category_result.deleted_count > 0:
                        logger.info(f"Successfully removed category '{category_name}' and {delete_products_result.deleted_count} products")
                        return True
                    return False
                    
        except Exception as e:
            logger.error(f"Error removing category and its products: {e}")
            return False

    def get_all_categories(self):
        """Get all categories from the database."""
        try:
            # Find all categories and sort them alphabetically
            categories = list(self.categories.find({}).sort('name', 1))
            return [cat['name'] for cat in categories]
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []

    def ensure_category_exists(self, category_name):
        """Ensure a category exists in the database."""
        try:
            # Try to insert if not exists
            self.categories.update_one(
                {'name': category_name},
                {
                    '$setOnInsert': {
                        'name': category_name,
                        'created_at': datetime.now(),
                        'updated_at': datetime.now()
                    }
                },
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error ensuring category exists: {e}")
            return False

    def add_product(self, product_data, category):
        """Add a new product to the database."""
        try:
            # Ensure category exists
            if not self.categories.find_one({'name': category}):
                # Create category if it doesn't exist
                self.add_category(category)
            
            # Add category to product data
            product_data['category'] = category
            product_data['created_at'] = datetime.now()
            product_data['updated_at'] = datetime.now()
            
            result = self.products.insert_one(product_data)
            return str(result.inserted_id) if result.inserted_id else None
        except Exception as e:
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

    def ping(self):
        """Test database connection."""
        try:
            # Try to execute a simple command
            self.db.command('ping')
            return True
        except PyMongoError as e:
            logger.error(f"Database ping failed: {e}")
            raise

    def reconnect(self):
        """Reconnect to the database."""
        try:
            # Close existing connection if any
            try:
                self.client.close()
            except:
                pass

            # Create new connection
            self.client = MongoClient(
                "mongodb+srv://krunalkanzariya:krunalkanzariya@primelinks.p0aov5y.mongodb.net/?retryWrites=true&w=majority&appName=primelinks",
                serverSelectionTimeoutMS=5000  # 5 second timeout
            )
            self.db = self.client.primelinks
            
            # Verify connection
            self.ping()
            
            # Recreate collections references
            self.users = self.db.users
            self.products = self.db.products
            self.categories = self.db.categories
            
            logger.info("Successfully reconnected to MongoDB")
            return True
        except PyMongoError as e:
            logger.error(f"Failed to reconnect to MongoDB: {e}")
            raise 
