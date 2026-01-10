# Filename    : cache.py
# Author      : Jon Kelley <jon.kelley@kzoomakers.org>
# Description : Thread-safe JSON file cache manager for multi-worker environments

import json
import os
import time
import fcntl
from datetime import datetime, timedelta
from pathlib import Path
import logging
import glob

# Default cache configuration
CACHE_DIR = os.environ.get('CACHE_DIR', '/tmp/door_control_cache')
DEFAULT_TTL = int(os.environ.get('CACHE_TTL', '1800'))  # 30 minutes in seconds
CACHE_ENABLED = os.environ.get('CACHE_ENABLED', 'true').lower() == 'true'


class CacheManager:
    """Thread-safe JSON file cache manager for multi-worker environments"""
    
    def __init__(self, cache_dir=CACHE_DIR, enabled=CACHE_ENABLED):
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled
        self.logger = logging.getLogger(__name__)
        
        # Statistics tracking
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'invalidations': 0,
            'errors': 0
        }
        
        # Create cache directory if it doesn't exist
        if self.enabled:
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Cache initialized at {self.cache_dir}")
            except Exception as e:
                self.logger.error(f"Failed to create cache directory: {str(e)}")
                self.enabled = False
    
    def get(self, cache_key, ttl=DEFAULT_TTL):
        """
        Get cached data if valid, None otherwise
        
        Args:
            cache_key: Unique identifier for the cached data
            ttl: Time to live in seconds (default: 1800 = 30 minutes)
            
        Returns:
            Cached data if valid and not expired, None otherwise
        """
        if not self.enabled:
            return None
        
        try:
            filepath = self._get_cache_filepath(cache_key)
            
            if not filepath.exists():
                self.stats['misses'] += 1
                self.logger.debug(f"Cache MISS: {cache_key} (file not found)")
                return None
            
            # Read cache file with shared lock
            cache_entry = self._read_cache_file(filepath)
            
            if cache_entry is None:
                self.stats['misses'] += 1
                self.logger.debug(f"Cache MISS: {cache_key} (invalid file)")
                return None
            
            # Check if cache entry has expired
            expires_at = datetime.fromisoformat(cache_entry['expires_at'])
            if datetime.utcnow() > expires_at:
                self.stats['misses'] += 1
                self.logger.debug(f"Cache MISS: {cache_key} (expired)")
                # Clean up expired cache file
                try:
                    filepath.unlink()
                except Exception:
                    pass
                return None
            
            # Cache hit!
            self.stats['hits'] += 1
            self.logger.info(f"Cache HIT: {cache_key}")
            return cache_entry['data']
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"Cache error on get({cache_key}): {str(e)}", exc_info=True)
            return None
    
    def set(self, cache_key, data, ttl=DEFAULT_TTL):
        """
        Store data in cache with expiration
        
        Args:
            cache_key: Unique identifier for the cached data
            data: Data to cache (must be JSON serializable)
            ttl: Time to live in seconds (default: 1800 = 30 minutes)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            filepath = self._get_cache_filepath(cache_key)
            
            # Create cache entry with metadata
            cache_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'expires_at': (datetime.utcnow() + timedelta(seconds=ttl)).isoformat(),
                'cache_key': cache_key,
                'ttl': ttl,
                'data': data
            }
            
            # Write cache file with exclusive lock
            self._write_cache_file(filepath, cache_entry)
            
            self.stats['sets'] += 1
            self.logger.debug(f"Cache SET: {cache_key}, TTL: {ttl}s")
            return True
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"Cache error on set({cache_key}): {str(e)}", exc_info=True)
            return False
    
    def invalidate(self, cache_key):
        """
        Remove specific cache entry
        
        Args:
            cache_key: Unique identifier for the cached data
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            filepath = self._get_cache_filepath(cache_key)
            
            if filepath.exists():
                filepath.unlink()
                self.stats['invalidations'] += 1
                self.logger.debug(f"Cache INVALIDATE: {cache_key}")
                return True
            else:
                self.logger.debug(f"Cache INVALIDATE: {cache_key} (not found)")
                return False
                
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"Cache error on invalidate({cache_key}): {str(e)}", exc_info=True)
            return False
    
    def invalidate_pattern(self, pattern):
        """
        Remove cache entries matching glob pattern
        
        Args:
            pattern: Glob pattern to match cache keys (e.g., "controller_*")
            
        Returns:
            Number of cache entries invalidated
        """
        if not self.enabled:
            return 0
        
        try:
            count = 0
            pattern_path = self.cache_dir / f"{pattern}.json"
            
            for filepath in glob.glob(str(pattern_path)):
                try:
                    Path(filepath).unlink()
                    count += 1
                    self.stats['invalidations'] += 1
                except Exception as e:
                    self.logger.warning(f"Failed to delete {filepath}: {str(e)}")
            
            self.logger.debug(f"Cache INVALIDATE PATTERN: {pattern} ({count} entries)")
            return count
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"Cache error on invalidate_pattern({pattern}): {str(e)}", exc_info=True)
            return 0
    
    def clear_all(self):
        """
        Clear entire cache directory
        
        Returns:
            Number of cache entries cleared
        """
        if not self.enabled:
            return 0
        
        try:
            count = 0
            for filepath in self.cache_dir.glob('*.json'):
                try:
                    filepath.unlink()
                    count += 1
                    self.stats['invalidations'] += 1
                except Exception as e:
                    self.logger.warning(f"Failed to delete {filepath}: {str(e)}")
            
            self.logger.info(f"Cache CLEAR ALL: {count} entries removed")
            return count
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"Cache error on clear_all(): {str(e)}", exc_info=True)
            return 0
    
    def get_stats(self):
        """
        Return cache statistics
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        # Get cache directory size and file count
        cache_size = 0
        file_count = 0
        if self.enabled and self.cache_dir.exists():
            for filepath in self.cache_dir.glob('*.json'):
                try:
                    cache_size += filepath.stat().st_size
                    file_count += 1
                except Exception:
                    pass
        
        return {
            'enabled': self.enabled,
            'cache_dir': str(self.cache_dir),
            'total_requests': total_requests,
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate': f"{hit_rate:.2f}%",
            'sets': self.stats['sets'],
            'invalidations': self.stats['invalidations'],
            'errors': self.stats['errors'],
            'cache_size_bytes': cache_size,
            'cache_size_mb': f"{cache_size / 1024 / 1024:.2f}",
            'file_count': file_count
        }
    
    def _get_cache_filepath(self, cache_key):
        """Get the file path for a cache key"""
        # Sanitize cache key to be filesystem-safe
        safe_key = cache_key.replace('/', '_').replace('\\', '_')
        return self.cache_dir / f"{safe_key}.json"
    
    def _read_cache_file(self, filepath):
        """
        Read cache file with shared lock
        
        Args:
            filepath: Path to cache file
            
        Returns:
            Cache entry dictionary or None if error
        """
        try:
            with open(filepath, 'r') as f:
                # Acquire shared lock for reading (multiple readers allowed)
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    # Release lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.debug(f"Failed to read cache file {filepath}: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error reading cache file {filepath}: {str(e)}")
            return None
    
    def _write_cache_file(self, filepath, data):
        """
        Write cache file with exclusive lock using atomic operation
        
        Args:
            filepath: Path to cache file
            data: Data to write (must be JSON serializable)
        """
        # Write to temporary file first, then atomically rename
        temp_file = filepath.with_suffix('.tmp')
        
        try:
            with open(temp_file, 'w') as f:
                # Acquire exclusive lock for writing (no other readers or writers)
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(data, f, indent=2)
                    f.flush()
                    # Ensure data is written to disk
                    os.fsync(f.fileno())
                finally:
                    # Release lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            
            # Atomic rename (replaces existing file if present)
            temp_file.replace(filepath)
            
        except Exception as e:
            # Clean up temp file if it exists
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            raise


# Global cache manager instance
cache_manager = CacheManager()
