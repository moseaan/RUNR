"""
MongoDB state persistence module for auto promo job management.
Provides reliable state storage for resuming jobs after server restart.
"""

import os
import datetime
import traceback
from typing import Optional, Dict, Any, List

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    print("Warning: pymongo not installed. Install with: pip install pymongo")

# MongoDB connection settings - can be overridden via environment variables
MONGO_URI = os.environ.get('MONGODB_URI', os.environ.get('MONGO_URI', 'mongodb://localhost:27017'))
MONGO_DB_NAME = os.environ.get('MONGO_DB_NAME', 'runr_app')

# Collection names
COLLECTION_ACTIVE_JOBS = 'active_jobs'
COLLECTION_JOB_STATES = 'job_states'
COLLECTION_SERVICES = 'services_catalog'
COLLECTION_PROFILES = 'profiles'
COLLECTION_MONITOR_TARGETS = 'monitor_targets'
COLLECTION_MONITOR_CONFIG = 'monitor_config'

# Global connection (lazy initialized)
_mongo_client: Optional['MongoClient'] = None
_mongo_db = None


def get_mongo_db():
    """Get MongoDB database connection (lazy initialization)."""
    global _mongo_client, _mongo_db
    
    if not PYMONGO_AVAILABLE:
        return None
    
    if _mongo_db is not None:
        return _mongo_db
    
    try:
        _mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # Test connection
        _mongo_client.admin.command('ping')
        _mongo_db = _mongo_client[MONGO_DB_NAME]
        print(f"✅ Connected to MongoDB: {MONGO_DB_NAME}")
        
        # Create indexes for efficient queries
        _mongo_db[COLLECTION_ACTIVE_JOBS].create_index('job_id', unique=True)
        _mongo_db[COLLECTION_JOB_STATES].create_index('job_id', unique=True)
        _mongo_db[COLLECTION_SERVICES].create_index([('platform', 1), ('service_category', 1)])
        _mongo_db[COLLECTION_PROFILES].create_index('name', unique=True)
        _mongo_db[COLLECTION_MONITOR_TARGETS].create_index('id', unique=True)
        _mongo_db[COLLECTION_MONITOR_CONFIG].create_index('config_key', unique=True)
        
        return _mongo_db
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"⚠️ MongoDB connection failed: {e}")
        print("   Auto promo resume will not work across server restarts.")
        _mongo_client = None
        _mongo_db = None
        return None
    except Exception as e:
        print(f"⚠️ MongoDB error: {e}")
        _mongo_client = None
        _mongo_db = None
        return None


def is_mongo_available() -> bool:
    """Check if MongoDB is available and connected."""
    db = get_mongo_db()
    return db is not None


# === Active Jobs Functions (for app.py) ===

def save_active_job(job_id: str, job_info: dict) -> bool:
    """Save a single active job to MongoDB."""
    db = get_mongo_db()
    if db is None:
        return False
    
    try:
        doc = {
            'job_id': job_id,
            **job_info,
            'updated_at': datetime.datetime.utcnow()
        }
        db[COLLECTION_ACTIVE_JOBS].update_one(
            {'job_id': job_id},
            {'$set': doc},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Warning: Could not save active job {job_id} to MongoDB: {e}")
        return False


def remove_active_job(job_id: str) -> bool:
    """Remove a job from active jobs (when completed/stopped)."""
    db = get_mongo_db()
    if db is None:
        return False
    
    try:
        db[COLLECTION_ACTIVE_JOBS].delete_one({'job_id': job_id})
        return True
    except Exception as e:
        print(f"Warning: Could not remove active job {job_id} from MongoDB: {e}")
        return False


def get_all_active_jobs() -> Dict[str, dict]:
    """Get all active jobs from MongoDB for resume on startup."""
    db = get_mongo_db()
    if db is None:
        return {}
    
    try:
        jobs = {}
        terminal_statuses = {'success', 'failed', 'stopped'}
        
        for doc in db[COLLECTION_ACTIVE_JOBS].find():
            job_id = doc.get('job_id')
            status = (doc.get('status') or '').lower()
            
            # Only return non-terminal jobs
            if job_id and status not in terminal_statuses:
                # Remove MongoDB-specific fields
                doc.pop('_id', None)
                doc.pop('job_id', None)
                jobs[job_id] = doc
        
        return jobs
    except Exception as e:
        print(f"Warning: Could not load active jobs from MongoDB: {e}")
        return {}


def clear_completed_jobs() -> int:
    """Remove all completed/failed/stopped jobs from active jobs collection."""
    db = get_mongo_db()
    if db is None:
        return 0
    
    try:
        result = db[COLLECTION_ACTIVE_JOBS].delete_many({
            'status': {'$in': ['success', 'failed', 'stopped']}
        })
        return result.deleted_count
    except Exception as e:
        print(f"Warning: Could not clear completed jobs: {e}")
        return 0


# === Job State Functions (for api_runner.py) ===

def save_job_state(job_id: str, state: dict) -> bool:
    """Save job execution state to MongoDB for resume capability."""
    db = get_mongo_db()
    if db is None:
        return False
    
    try:
        doc = {
            'job_id': job_id,
            **state,
            'last_updated': datetime.datetime.utcnow()
        }
        db[COLLECTION_JOB_STATES].update_one(
            {'job_id': job_id},
            {'$set': doc},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Warning: Could not save job state for {job_id} to MongoDB: {e}")
        return False


def load_job_state(job_id: str) -> dict:
    """Load saved job execution state from MongoDB."""
    db = get_mongo_db()
    if db is None:
        return {}
    
    try:
        doc = db[COLLECTION_JOB_STATES].find_one({'job_id': job_id})
        if doc:
            doc.pop('_id', None)
            doc.pop('job_id', None)
            return doc
        return {}
    except Exception as e:
        print(f"Warning: Could not load job state for {job_id} from MongoDB: {e}")
        return {}


def clear_job_state(job_id: str) -> bool:
    """Clear job state after completion."""
    db = get_mongo_db()
    if db is None:
        return False
    
    try:
        db[COLLECTION_JOB_STATES].delete_one({'job_id': job_id})
        return True
    except Exception as e:
        print(f"Warning: Could not clear job state for {job_id} from MongoDB: {e}")
        return False


def get_resumable_jobs() -> List[dict]:
    """Get all jobs that can be resumed (have saved state and aren't completed)."""
    db = get_mongo_db()
    if db is None:
        return []
    
    try:
        resumable = []
        for doc in db[COLLECTION_JOB_STATES].find():
            job_id = doc.get('job_id')
            if job_id:
                # Check if this job is still in active jobs and not terminal
                active_job = db[COLLECTION_ACTIVE_JOBS].find_one({'job_id': job_id})
                if active_job:
                    status = (active_job.get('status') or '').lower()
                    if status not in {'success', 'failed', 'stopped'}:
                        doc.pop('_id', None)
                        resumable.append(doc)
        return resumable
    except Exception as e:
        print(f"Warning: Could not get resumable jobs: {e}")
        return []


# === Cleanup Functions ===

def cleanup_old_states(days: int = 7) -> int:
    """Remove job states older than specified days."""
    db = get_mongo_db()
    if db is None:
        return 0
    
    try:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        result = db[COLLECTION_JOB_STATES].delete_many({
            'last_updated': {'$lt': cutoff}
        })
        return result.deleted_count
    except Exception as e:
        print(f"Warning: Could not cleanup old states: {e}")
        return 0


# === Services Catalog Functions ===

# In-memory cache for services
_services_cache: Optional[List[Dict[str, Any]]] = None
_services_cache_time: Optional[datetime.datetime] = None
SERVICES_CACHE_TTL_SECONDS = 300  # 5 minutes


def save_services_to_mongo(services: List[Dict[str, Any]]) -> bool:
    """Save all services to MongoDB, replacing existing data."""
    global _services_cache, _services_cache_time
    db = get_mongo_db()
    if db is None:
        return False
    
    try:
        # Clear existing services and insert new ones
        db[COLLECTION_SERVICES].delete_many({})
        if services:
            # Add timestamps to each service
            docs = []
            for svc in services:
                doc = {**svc, 'updated_at': datetime.datetime.utcnow()}
                docs.append(doc)
            db[COLLECTION_SERVICES].insert_many(docs)
        
        # Update cache
        _services_cache = services
        _services_cache_time = datetime.datetime.utcnow()
        print(f"✅ Saved {len(services)} services to MongoDB")
        return True
    except Exception as e:
        print(f"Warning: Could not save services to MongoDB: {e}")
        return False


def load_services_from_mongo(refresh: bool = False) -> Optional[List[Dict[str, Any]]]:
    """Load services from MongoDB with caching."""
    global _services_cache, _services_cache_time
    
    # Check cache first (unless refresh requested)
    if not refresh and _services_cache is not None and _services_cache_time is not None:
        cache_age = (datetime.datetime.utcnow() - _services_cache_time).total_seconds()
        if cache_age < SERVICES_CACHE_TTL_SECONDS:
            return _services_cache
    
    db = get_mongo_db()
    if db is None:
        return None
    
    try:
        services = []
        for doc in db[COLLECTION_SERVICES].find():
            doc.pop('_id', None)
            doc.pop('updated_at', None)
            services.append(doc)
        
        # Update cache
        _services_cache = services
        _services_cache_time = datetime.datetime.utcnow()
        return services
    except Exception as e:
        print(f"Warning: Could not load services from MongoDB: {e}")
        return None


def update_service_in_mongo(platform: str, service_category: str, service_data: Dict[str, Any]) -> bool:
    """Update or insert a single service in MongoDB."""
    global _services_cache, _services_cache_time
    db = get_mongo_db()
    if db is None:
        return False
    
    try:
        doc = {
            **service_data,
            'platform': platform,
            'service_category': service_category,
            'updated_at': datetime.datetime.utcnow()
        }
        # Remove existing services for this platform+category and insert new one
        db[COLLECTION_SERVICES].delete_many({
            'platform': platform,
            'service_category': service_category
        })
        db[COLLECTION_SERVICES].insert_one(doc)
        
        # Invalidate cache
        _services_cache = None
        _services_cache_time = None
        return True
    except Exception as e:
        print(f"Warning: Could not update service in MongoDB: {e}")
        return False


def clear_services_cache():
    """Clear the in-memory services cache."""
    global _services_cache, _services_cache_time
    _services_cache = None
    _services_cache_time = None


# === Profiles Functions ===

# In-memory cache for profiles
_profiles_cache: Optional[Dict[str, Any]] = None
_profiles_cache_time: Optional[datetime.datetime] = None
PROFILES_CACHE_TTL_SECONDS = 300  # 5 minutes


def save_profiles_to_mongo(profiles: Dict[str, Any]) -> bool:
    """Save all profiles to MongoDB, replacing existing data."""
    global _profiles_cache, _profiles_cache_time
    db = get_mongo_db()
    if db is None:
        return False
    
    try:
        # Clear existing profiles and insert new ones
        db[COLLECTION_PROFILES].delete_many({})
        if profiles:
            docs = []
            for name, data in profiles.items():
                doc = {
                    'name': name,
                    'data': data,
                    'updated_at': datetime.datetime.utcnow()
                }
                docs.append(doc)
            db[COLLECTION_PROFILES].insert_many(docs)
        
        # Update cache
        _profiles_cache = profiles
        _profiles_cache_time = datetime.datetime.utcnow()
        print(f"✅ Saved {len(profiles)} profiles to MongoDB")
        return True
    except Exception as e:
        print(f"Warning: Could not save profiles to MongoDB: {e}")
        return False


def load_profiles_from_mongo(refresh: bool = False) -> Optional[Dict[str, Any]]:
    """Load profiles from MongoDB with caching."""
    global _profiles_cache, _profiles_cache_time
    
    # Check cache first (unless refresh requested)
    if not refresh and _profiles_cache is not None and _profiles_cache_time is not None:
        cache_age = (datetime.datetime.utcnow() - _profiles_cache_time).total_seconds()
        if cache_age < PROFILES_CACHE_TTL_SECONDS:
            return _profiles_cache
    
    db = get_mongo_db()
    if db is None:
        return None
    
    try:
        profiles = {}
        for doc in db[COLLECTION_PROFILES].find():
            name = doc.get('name')
            data = doc.get('data')
            if name and data:
                profiles[name] = data
        
        # Update cache
        _profiles_cache = profiles
        _profiles_cache_time = datetime.datetime.utcnow()
        return profiles
    except Exception as e:
        print(f"Warning: Could not load profiles from MongoDB: {e}")
        return None


def save_single_profile_to_mongo(name: str, data: Dict[str, Any]) -> bool:
    """Save or update a single profile in MongoDB."""
    global _profiles_cache, _profiles_cache_time
    db = get_mongo_db()
    if db is None:
        return False
    
    try:
        doc = {
            'name': name,
            'data': data,
            'updated_at': datetime.datetime.utcnow()
        }
        db[COLLECTION_PROFILES].update_one(
            {'name': name},
            {'$set': doc},
            upsert=True
        )
        
        # Invalidate cache
        _profiles_cache = None
        _profiles_cache_time = None
        return True
    except Exception as e:
        print(f"Warning: Could not save profile {name} to MongoDB: {e}")
        return False


def delete_profile_from_mongo(name: str) -> bool:
    """Delete a profile from MongoDB."""
    global _profiles_cache, _profiles_cache_time
    db = get_mongo_db()
    if db is None:
        return False
    
    try:
        result = db[COLLECTION_PROFILES].delete_one({'name': name})
        # Invalidate cache
        _profiles_cache = None
        _profiles_cache_time = None
        return result.deleted_count > 0
    except Exception as e:
        print(f"Warning: Could not delete profile {name} from MongoDB: {e}")
        return False


def clear_profiles_cache():
    """Clear the in-memory profiles cache."""
    global _profiles_cache, _profiles_cache_time
    _profiles_cache = None
    _profiles_cache_time = None


# === Monitor Targets Functions ===

# In-memory cache for monitor config
_monitor_config_cache: Optional[Dict[str, Any]] = None
_monitor_config_cache_time: Optional[datetime.datetime] = None
MONITOR_CACHE_TTL_SECONDS = 60  # 1 minute (shorter because monitoring state changes frequently)


def save_monitor_config_to_mongo(config: Dict[str, Any]) -> bool:
    """Save monitoring configuration to MongoDB."""
    global _monitor_config_cache, _monitor_config_cache_time
    db = get_mongo_db()
    if db is None:
        return False
    
    try:
        # Save polling interval separately
        polling_interval = config.get('polling_interval_seconds', 300)
        db[COLLECTION_MONITOR_CONFIG].update_one(
            {'config_key': 'polling_interval'},
            {'$set': {'config_key': 'polling_interval', 'value': polling_interval, 'updated_at': datetime.datetime.utcnow()}},
            upsert=True
        )
        
        # Save targets
        targets = config.get('targets', [])
        db[COLLECTION_MONITOR_TARGETS].delete_many({})
        if targets:
            docs = []
            for target in targets:
                doc = {**target, 'updated_at': datetime.datetime.utcnow()}
                docs.append(doc)
            db[COLLECTION_MONITOR_TARGETS].insert_many(docs)
        
        # Update cache
        _monitor_config_cache = config
        _monitor_config_cache_time = datetime.datetime.utcnow()
        print(f"✅ Saved monitor config with {len(targets)} targets to MongoDB")
        return True
    except Exception as e:
        print(f"Warning: Could not save monitor config to MongoDB: {e}")
        return False


def load_monitor_config_from_mongo(refresh: bool = False) -> Optional[Dict[str, Any]]:
    """Load monitoring configuration from MongoDB with caching."""
    global _monitor_config_cache, _monitor_config_cache_time
    
    # Check cache first (unless refresh requested)
    if not refresh and _monitor_config_cache is not None and _monitor_config_cache_time is not None:
        cache_age = (datetime.datetime.utcnow() - _monitor_config_cache_time).total_seconds()
        if cache_age < MONITOR_CACHE_TTL_SECONDS:
            return _monitor_config_cache
    
    db = get_mongo_db()
    if db is None:
        return None
    
    try:
        # Load polling interval
        config_doc = db[COLLECTION_MONITOR_CONFIG].find_one({'config_key': 'polling_interval'})
        polling_interval = config_doc.get('value', 300) if config_doc else 300
        
        # Load targets
        targets = []
        for doc in db[COLLECTION_MONITOR_TARGETS].find():
            doc.pop('_id', None)
            doc.pop('updated_at', None)
            targets.append(doc)
        
        config = {
            'polling_interval_seconds': polling_interval,
            'targets': targets
        }
        
        # Update cache
        _monitor_config_cache = config
        _monitor_config_cache_time = datetime.datetime.utcnow()
        return config
    except Exception as e:
        print(f"Warning: Could not load monitor config from MongoDB: {e}")
        return None


def save_monitor_target_to_mongo(target: Dict[str, Any]) -> bool:
    """Save or update a single monitor target in MongoDB."""
    global _monitor_config_cache, _monitor_config_cache_time
    db = get_mongo_db()
    if db is None:
        return False
    
    try:
        target_id = target.get('id')
        if not target_id:
            return False
        
        doc = {**target, 'updated_at': datetime.datetime.utcnow()}
        db[COLLECTION_MONITOR_TARGETS].update_one(
            {'id': target_id},
            {'$set': doc},
            upsert=True
        )
        
        # Invalidate cache
        _monitor_config_cache = None
        _monitor_config_cache_time = None
        return True
    except Exception as e:
        print(f"Warning: Could not save monitor target to MongoDB: {e}")
        return False


def delete_monitor_target_from_mongo(target_id: str) -> bool:
    """Delete a monitor target from MongoDB."""
    global _monitor_config_cache, _monitor_config_cache_time
    db = get_mongo_db()
    if db is None:
        return False
    
    try:
        result = db[COLLECTION_MONITOR_TARGETS].delete_one({'id': target_id})
        # Invalidate cache
        _monitor_config_cache = None
        _monitor_config_cache_time = None
        return result.deleted_count > 0
    except Exception as e:
        print(f"Warning: Could not delete monitor target from MongoDB: {e}")
        return False


def get_monitor_target_from_mongo(target_id: str) -> Optional[Dict[str, Any]]:
    """Get a single monitor target from MongoDB."""
    db = get_mongo_db()
    if db is None:
        return None
    
    try:
        doc = db[COLLECTION_MONITOR_TARGETS].find_one({'id': target_id})
        if doc:
            doc.pop('_id', None)
            doc.pop('updated_at', None)
            return doc
        return None
    except Exception as e:
        print(f"Warning: Could not get monitor target from MongoDB: {e}")
        return None


def clear_monitor_cache():
    """Clear the in-memory monitor config cache."""
    global _monitor_config_cache, _monitor_config_cache_time
    _monitor_config_cache = None
    _monitor_config_cache_time = None
