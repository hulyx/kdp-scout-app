"""
Automated Product Creation Worker for POD Platforms
Handles uploading designs to Redbubble, Spreadshirt, and Zazzle
"""
from scout.gui.workers.base_worker import BaseWorker
from PyQt6.QtCore import pyqtSignal, QThread
import os
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback


class PlatformUploader:
    """Base class for platform-specific uploaders"""
    
    def __init__(self, platform_name):
        self.platform_name = platform_name
        self.is_paused = False
        self.is_stopped = False
        self.pause_event = threading.Event()
        self.pause_event.set()  # Initially not paused
        
    def pause(self):
        self.is_paused = True
        self.pause_event.clear()
        
    def resume(self):
        self.is_paused = False
        self.pause_event.set()
        
    def stop(self):
        self.is_stopped = True
        self.pause_event.set()  # Unblock if waiting
        
    def wait_if_paused(self):
        """Block execution while paused"""
        self.pause_event.wait()
        
    def check_stopped(self):
        """Check if upload should be stopped"""
        return self.is_stopped


class RedbubbleUploader(PlatformUploader):
    """Handles Redbubble product uploads"""
    
    def __init__(self):
        super().__init__("Redbubble")
        self.designs_uploaded = []
        self.errors = []
        
    def upload_design(self, design_path, title, tags, description, products=None):
        """
        Upload a design to Redbubble
        
        Args:
            design_path: Path to the image file
            title: Product title
            tags: List of tags
            description: Product description
            products: List of product types to enable
            
        Returns:
            dict with success status and details
        """
        self.wait_if_paused()
        if self.check_stopped():
            return {"success": False, "reason": "stopped"}
            
        try:
            # Simulate upload process (in real implementation, this would use Selenium or API)
            result = {
                "success": True,
                "platform": "Redbubble",
                "design": os.path.basename(design_path),
                "title": title,
                "url": f"https://redbubble.com/products/{int(time.time())}",
                "timestamp": time.time()
            }
            self.designs_uploaded.append(result)
            return result
        except Exception as e:
            error = {
                "platform": "Redbubble",
                "design": os.path.basename(design_path),
                "error": str(e)
            }
            self.errors.append(error)
            return {"success": False, "error": str(e)}


class SpreadshirtUploader(PlatformUploader):
    """Handles Spreadshirt product uploads"""
    
    def __init__(self):
        super().__init__("Spreadshirt")
        self.designs_uploaded = []
        self.errors = []
        
    def upload_design(self, design_path, title, tags, description, products=None):
        """Upload a design to Spreadshirt"""
        self.wait_if_paused()
        if self.check_stopped():
            return {"success": False, "reason": "stopped"}
            
        try:
            result = {
                "success": True,
                "platform": "Spreadshirt",
                "design": os.path.basename(design_path),
                "title": title,
                "url": f"https://spreadshirt.com/products/{int(time.time())}",
                "timestamp": time.time()
            }
            self.designs_uploaded.append(result)
            return result
        except Exception as e:
            error = {
                "platform": "Spreadshirt",
                "design": os.path.basename(design_path),
                "error": str(e)
            }
            self.errors.append(error)
            return {"success": False, "error": str(e)}


class ZazzleUploader(PlatformUploader):
    """Handles Zazzle product uploads"""
    
    def __init__(self):
        super().__init__("Zazzle")
        self.designs_uploaded = []
        self.errors = []
        
    def upload_design(self, design_path, title, tags, description, products=None):
        """Upload a design to Zazzle"""
        self.wait_if_paused()
        if self.check_stopped():
            return {"success": False, "reason": "stopped"}
            
        try:
            result = {
                "success": True,
                "platform": "Zazzle",
                "design": os.path.basename(design_path),
                "title": title,
                "url": f"https://zazzle.com/products/{int(time.time())}",
                "timestamp": time.time()
            }
            self.designs_uploaded.append(result)
            return result
        except Exception as e:
            error = {
                "platform": "Zazzle",
                "design": os.path.basename(design_path),
                "error": str(e)
            }
            self.errors.append(error)
            return {"success": False, "error": str(e)}


class AutoResizeHelper:
    """Handles automatic design resizing for different platforms"""
    
    PLATFORM_REQUIREMENTS = {
        "Redbubble": {
            "min_width": 2400,
            "min_height": 3200,
            "dpi": 150,
            "format": "PNG"
        },
        "Spreadshirt": {
            "min_width": 1800,
            "min_height": 2400,
            "dpi": 150,
            "format": "PNG"
        },
        "Zazzle": {
            "min_width": 2000,
            "min_height": 2400,
            "dpi": 150,
            "format": "PNG"
        }
    }
    
    @classmethod
    def get_requirements(cls, platform):
        return cls.PLATFORM_REQUIREMENTS.get(platform, {})
    
    @classmethod
    def resize_for_platform(cls, image_path, platform, output_path=None):
        """
        Resize an image to meet platform requirements
        
        Args:
            image_path: Path to source image
            platform: Target platform name
            output_path: Optional output path (default: auto-generate)
            
        Returns:
            Path to resized image
        """
        try:
            from PIL import Image
            
            img = Image.open(image_path)
            reqs = cls.get_requirements(platform)
            
            min_width = reqs.get("min_width", 2400)
            min_height = reqs.get("min_height", 3200)
            
            # Calculate new dimensions maintaining aspect ratio
            width, height = img.size
            ratio = max(min_width / width, min_height / height)
            
            if ratio > 1:
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            if output_path is None:
                base = Path(image_path)
                output_path = base.parent / f"{base.stem}_{platform}{base.suffix}"
            
            img.save(output_path, dpi=(reqs.get("dpi", 150), reqs.get("dpi", 150)))
            return str(output_path)
            
        except ImportError:
            # PIL not available, return original path
            return image_path
        except Exception:
            return image_path


class DesignArchive:
    """Tracks which designs have been uploaded to which platforms"""
    
    def __init__(self, db_path=None):
        from scout.config import Config
        self.db_path = db_path or Config.get_db_path().parent / "design_archive.json"
        self._archive = self._load_archive()
        
    def _load_archive(self):
        """Load archive from JSON file"""
        import json
        try:
            if os.path.exists(self.db_path):
                with open(self.db_path, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {"designs": {}}
    
    def _save_archive(self):
        """Save archive to JSON file"""
        import json
        try:
            with open(self.db_path, 'w') as f:
                json.dump(self._archive, f, indent=2)
        except Exception:
            pass
    
    def is_uploaded(self, design_path, platform):
        """Check if a design was already uploaded to a platform"""
        design_key = str(Path(design_path).resolve())
        return platform in self._archive["designs"].get(design_key, {}).get("platforms", [])
    
    def mark_uploaded(self, design_path, platform, url=None, title=None):
        """Mark a design as uploaded to a platform"""
        import time
        design_key = str(Path(design_path).resolve())
        
        if design_key not in self._archive["designs"]:
            self._archive["designs"][design_key] = {
                "path": design_key,
                "platforms": {},
                "first_upload": time.time()
            }
        
        self._archive["designs"][design_key]["platforms"][platform] = {
            "url": url,
            "title": title,
            "uploaded_at": time.time()
        }
        self._save_archive()
    
    def get_design_history(self, design_path):
        """Get upload history for a design"""
        design_key = str(Path(design_path).resolve())
        return self._archive["designs"].get(design_key, {})
    
    def get_all_uploaded(self, platform=None):
        """Get all designs uploaded to a platform (or all platforms)"""
        results = []
        for design_key, info in self._archive["designs"].items():
            if platform is None or platform in info.get("platforms", {}):
                results.append({
                    "path": design_key,
                    "platforms": list(info.get("platforms", {}).keys()),
                    "first_upload": info.get("first_upload")
                })
        return results


class PodProductCreatorWorker(BaseWorker):
    """
    Worker for automated product creation across multiple POD platforms.
    Handles parallel uploads with pause/resume/stop control.
    """
    
    # Signals for UI updates
    platform_progress = pyqtSignal(str, int)  # platform_name, percentage
    platform_status = pyqtSignal(str, str)    # platform_name, status_message
    upload_complete = pyqtSignal(dict)        # final report
    design_processed = pyqtSignal(dict)       # individual design result
    
    def __init__(self, designs, metadata, platforms=None, parent=None):
        """
        Initialize the worker
        
        Args:
            designs: List of design file paths
            metadata: Dict with title, tags, description templates
            platforms: List of platforms to upload to (default: all)
            parent: Parent QObject
        """
        super().__init__(parent)
        
        self.designs = designs
        self.metadata = metadata
        self.platforms = platforms or ["Redbubble", "Spreadshirt", "Zazzle"]
        
        # Initialize uploaders
        self.uploaders = {
            "Redbubble": RedbubbleUploader(),
            "Spreadshirt": SpreadshirtUploader(),
            "Zazzle": ZazzleUploader()
        }
        
        # Control flags
        self.is_paused = False
        self.is_stopped = False
        self.control_lock = threading.Lock()
        
        # Progress tracking
        self.total_designs = len(designs)
        self.processed_count = 0
        
        # Archive for tracking uploads
        self.archive = DesignArchive()
        
        # Adaptive rate limiting
        self.base_delay = 1.0  # Base delay between uploads
        self.current_delay = self.base_delay
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        
    def run_task(self):
        """Main upload task"""
        self.log.emit(f"Starting product creation for {len(self.designs)} designs")
        self.log.emit(f"Target platforms: {', '.join(self.platforms)}")
        
        results = {
            "total_designs": len(self.designs),
            "successful": [],
            "failed": [],
            "skipped": [],
            "by_platform": {p: {"success": 0, "failed": 0} for p in self.platforms}
        }
        
        # Process each design
        for i, design_path in enumerate(self.designs):
            if self.check_stopped():
                self.log.emit("Upload process stopped by user")
                break
                
            self.wait_if_paused()
            
            design_name = os.path.basename(design_path)
            self.status.emit(f"Processing: {design_name}")
            
            # Check if already uploaded
            skip_reasons = []
            for platform in self.platforms:
                if self.archive.is_uploaded(design_path, platform):
                    skip_reasons.append(platform)
            
            if skip_reasons:
                self.log.emit(f"Skipping {design_name} - already uploaded to: {', '.join(skip_reasons)}")
                results["skipped"].append({
                    "design": design_name,
                    "platforms": skip_reasons
                })
                continue
            
            # Auto-resize design for each platform
            resized_paths = {}
            for platform in self.platforms:
                try:
                    resized_path = AutoResizeHelper.resize_for_platform(design_path, platform)
                    resized_paths[platform] = resized_path
                except Exception as e:
                    self.log.emit(f"Resize warning for {platform}: {e}")
                    resized_paths[platform] = design_path
            
            # Upload to each platform in parallel
            platform_results = self._upload_to_platforms(
                design_path, 
                resized_paths,
                self.metadata
            )
            
            # Collect results
            design_result = {
                "design": design_name,
                "platforms": platform_results
            }
            self.design_processed.emit(design_result)
            
            for platform, result in platform_results.items():
                if result.get("success"):
                    results["successful"].append({
                        "design": design_name,
                        "platform": platform,
                        "url": result.get("url")
                    })
                    results["by_platform"][platform]["success"] += 1
                    
                    # Mark as uploaded in archive
                    self.archive.mark_uploaded(
                        design_path, 
                        platform, 
                        url=result.get("url"),
                        title=self.metadata.get("title", "")
                    )
                    
                    # Adjust delay on success
                    self._adjust_delay(success=True)
                else:
                    results["failed"].append({
                        "design": design_name,
                        "platform": platform,
                        "error": result.get("error", "Unknown error")
                    })
                    results["by_platform"][platform]["failed"] += 1
                    
                    # Adjust delay on failure
                    self._adjust_delay(success=False)
            
            self.processed_count += 1
            progress_pct = int((self.processed_count / self.total_designs) * 100)
            self.progress.emit(progress_pct, 100)
        
        # Emit final report
        self.log.emit("Upload process complete!")
        self.upload_complete.emit(results)
        return results
    
    def _upload_to_platforms(self, design_path, resized_paths, metadata):
        """Upload a design to all platforms in parallel"""
        
        def upload_single(platform):
            uploader = self.uploaders[platform]
            resize_path = resized_paths.get(platform, design_path)
            
            self.platform_status.emit(platform, f"Uploading {os.path.basename(design_path)}...")
            
            result = uploader.upload_design(
                design_path=resize_path,
                title=metadata.get("title", ""),
                tags=metadata.get("tags", []),
                description=metadata.get("description", ""),
                products=metadata.get("products")
            )
            
            self.platform_progress.emit(platform, 100)
            return platform, result
        
        # Use ThreadPoolExecutor for parallel uploads
        results = {}
        with ThreadPoolExecutor(max_workers=len(self.platforms)) as executor:
            futures = {executor.submit(upload_single, p): p for p in self.platforms}
            
            for future in as_completed(futures):
                platform = futures[future]
                try:
                    _, result = future.result(timeout=300)
                    results[platform] = result
                except Exception as e:
                    results[platform] = {
                        "success": False,
                        "error": str(e)
                    }
        
        return results
    
    def _adjust_delay(self, success=True):
        """Adaptively adjust upload delay based on success/failure rate"""
        with self.control_lock:
            if success:
                self.consecutive_successes += 1
                self.consecutive_failures = 0
                
                # Gradually decrease delay on consecutive successes
                if self.consecutive_successes >= 5 and self.current_delay > 0.5:
                    self.current_delay = max(0.5, self.current_delay * 0.9)
                    self.log.emit(f"Upload speed increased: {self.current_delay:.2f}s delay")
            else:
                self.consecutive_failures += 1
                self.consecutive_successes = 0
                
                # Increase delay on failures (platform might be slow)
                if self.consecutive_failures >= 2:
                    self.current_delay = min(10.0, self.current_delay * 1.5)
                    self.log.emit(f"Upload speed decreased: {self.current_delay:.2f}s delay (detected slow response)")
    
    def pause(self):
        """Pause all uploads"""
        with self.control_lock:
            self.is_paused = True
        for uploader in self.uploaders.values():
            uploader.pause()
        self.log.emit("Uploads paused")
    
    def resume(self):
        """Resume all uploads"""
        with self.control_lock:
            self.is_paused = False
        for uploader in self.uploaders.values():
            uploader.resume()
        self.log.emit("Uploads resumed")
    
    def stop(self):
        """Stop all uploads"""
        with self.control_lock:
            self.is_stopped = True
        for uploader in self.uploaders.values():
            uploader.stop()
        self.log.emit("Uploads stopped")
    
    def wait_if_paused(self):
        """Block execution while paused"""
        while self.is_paused and not self.is_stopped:
            time.sleep(0.5)
    
    def check_stopped(self):
        """Check if uploads should be stopped"""
        return self.is_stopped
    
    def get_status(self):
        """Get current upload status"""
        return {
            "processed": self.processed_count,
            "total": self.total_designs,
            "is_paused": self.is_paused,
            "is_stopped": self.is_stopped,
            "current_delay": self.current_delay
        }


class TagGenerator:
    """Helper for generating tags from titles and keywords"""
    
    COMMON_POD_TAGS = [
        "gift", "present", "funny", "cute", "cool", "awesome",
        "birthday", "christmas", "halloween", "valentines",
        "mom", "dad", "sister", "brother", "friend"
    ]
    
    @classmethod
    def generate_tags(cls, title, keywords=None, max_tags=50):
        """Generate tags from title and optional keywords"""
        tags = set()
        
        # Add words from title
        words = title.lower().split()
        for word in words:
            clean_word = ''.join(c for c in word if c.isalnum())
            if len(clean_word) > 2:
                tags.add(clean_word)
        
        # Add keyword phrases
        if keywords:
            for kw in keywords:
                tags.add(kw.lower().replace(' ', '_'))
        
        # Add common relevant tags
        for tag in cls.COMMON_POD_TAGS:
            if tag in title.lower():
                tags.add(tag)
        
        # Limit to max_tags
        return list(tags)[:max_tags]
