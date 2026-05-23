"""
Automated Product Creation Page for POD Platforms
Provides UI for uploading designs to Redbubble, Spreadshirt, and Zazzle
"""
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QGroupBox, QFormLayout, QLineEdit, QTextEdit, QComboBox,
    QSpinBox, QListWidget, QListWidgetItem, QProgressBar,
    QMessageBox, QFileDialog, QSplitter, QFrame, QScrollArea,
    QCheckBox, QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QIcon

from scout.gui.widgets.progress_panel import ProgressPanel
from scout.gui.helpers import make_header
from scout.gui.workers.product_creator_worker import (
    PodProductCreatorWorker, TagGenerator, DesignArchive
)


class PlatformStatusCard(QFrame):
    """Visual card showing upload status for a single platform"""
    
    def __init__(self, platform_name, parent=None):
        super().__init__(parent)
        self.platform_name = platform_name
        self.setProperty("class", "platform-card")
        self.setFixedHeight(120)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # Platform name
        self.name_label = QLabel(platform_name)
        self.name_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #cba6f7;")
        layout.addWidget(self.name_label)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #a6adc8; font-size: 12px;")
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        layout.addWidget(self.progress)
        
        # Success/Failed counters
        self.counters_label = QLabel("✓ 0  |  ✗ 0")
        self.counters_label.setStyleSheet("color: #6c7086; font-size: 11px;")
        layout.addWidget(self.counters_label)
    
    def update_status(self, status):
        """Update the status display"""
        self.status_label.setText(status)
    
    def update_progress(self, value):
        """Update progress bar"""
        self.progress.setValue(value)
    
    def update_counters(self, success, failed):
        """Update success/failed counters"""
        success_color = "#a6e3a1" if success > 0 else "#6c7086"
        failed_color = "#f38ba8" if failed > 0 else "#6c7086"
        self.counters_label.setText(
            f'<span style="color: {success_color};">✓ {success}</span>'
            f'  |  '
            f'<span style="color: {failed_color};">✗ {failed}</span>'
        )


class DesignItemWidget(QWidget):
    """Widget representing a single design in the list"""
    
    def __init__(self, design_path, parent=None):
        super().__init__(parent)
        self.design_path = design_path
        self.upload_status = {}  # platform -> status
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # Thumbnail placeholder
        self.thumbnail = QLabel()
        self.thumbnail.setFixedSize(60, 60)
        self.thumbnail.setStyleSheet("""
            background-color: #313244;
            border-radius: 4px;
            color: #6c7086;
        """)
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setText("🖼️")
        layout.addWidget(self.thumbnail)
        
        # Design info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        self.name_label = QLabel(os.path.basename(design_path))
        self.name_label.setStyleSheet("font-weight: bold; color: #cdd6f4;")
        self.name_label.setWordWrap(True)
        info_layout.addWidget(self.name_label)
        
        self.path_label = QLabel(str(Path(design_path).parent))
        self.path_label.setStyleSheet("color: #6c7086; font-size: 11px;")
        info_layout.addWidget(self.path_label)
        
        self.status_label = QLabel("Pending")
        self.status_label.setStyleSheet("color: #f9e2af; font-size: 11px;")
        info_layout.addWidget(self.status_label)
        
        info_layout.addStretch()
        layout.addLayout(info_layout, 1)
        
        # Platform badges
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(4)
        self.badges = {}
        for platform in ["Redbubble", "Spreadshirt", "Zazzle"]:
            badge = QLabel(f"● {platform}")
            badge.setStyleSheet("color: #6c7086; font-size: 10px; padding: 2px 6px;")
            badges_layout.addWidget(badge)
            self.badges[platform] = badge
        layout.addLayout(badges_layout)
    
    def update_platform_status(self, platform, success):
        """Update status badge for a platform"""
        if platform in self.badges:
            color = "#a6e3a1" if success else "#f38ba8"
            self.badges[platform].setStyleSheet(
                f"color: {color}; font-size: 10px; padding: 2px 6px;"
            )
        self.upload_status[platform] = success
    
    def set_overall_status(self, status):
        """Set overall status text"""
        self.status_label.setText(status)
        colors = {
            "Pending": "#f9e2af",
            "Uploading...": "#89b4fa",
            "Complete": "#a6e3a1",
            "Failed": "#f38ba8",
            "Skipped": "#6c7086"
        }
        self.status_label.setStyleSheet(f"color: {colors.get(status, '#cdd6f4')}; font-size: 11px;")


class UploadReportDialog(QDialog):
    """Dialog showing final upload report"""
    
    def __init__(self, report, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Upload Report")
        self.setMinimumSize(600, 500)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Title
        title = QLabel("📊 Upload Summary")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #cba6f7;")
        layout.addWidget(title)
        
        # Overall stats
        total = report.get("total_designs", 0)
        successful = len(report.get("successful", []))
        failed = len(report.get("failed", []))
        skipped = len(report.get("skipped", []))
        
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)
        
        stats = [
            ("Total Designs", total, "#cdd6f4"),
            ("Successful", successful, "#a6e3a1"),
            ("Failed", failed, "#f38ba8"),
            ("Skipped", skipped, "#6c7086")
        ]
        
        for label, value, color in stats:
            stat_box = QFrame()
            stat_box.setStyleSheet(f"background-color: #1e1e2e; border-radius: 8px; padding: 12px;")
            stat_layout = QVBoxLayout(stat_box)
            stat_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            val_label = QLabel(str(value))
            val_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")
            val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stat_layout.addWidget(val_label)
            
            lbl_label = QLabel(label)
            lbl_label.setStyleSheet("color: #6c7086; font-size: 12px;")
            lbl_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stat_layout.addWidget(lbl_label)
            
            stats_layout.addWidget(stat_box)
        
        layout.addLayout(stats_layout)
        
        # Platform breakdown
        platform_group = QGroupBox("By Platform")
        platform_layout = QFormLayout(platform_group)
        
        by_platform = report.get("by_platform", {})
        for platform, counts in by_platform.items():
            success = counts.get("success", 0)
            failed = counts.get("failed", 0)
            platform_layout.addRow(
                QLabel(f"{platform}:"),
                QLabel(f'✓ {success}  |  ✗ {failed}')
            )
        
        layout.addWidget(platform_group)
        
        # Successful uploads list
        if report.get("successful"):
            success_group = QGroupBox("Successfully Uploaded")
            success_layout = QVBoxLayout(success_group)
            success_list = QListWidget()
            success_list.setMaximumHeight(150)
            for item in report["successful"][:10]:
                item_text = f"✓ {item['design']} → {item['platform']}"
                success_list.addItem(item_text)
            if len(report["successful"]) > 10:
                success_list.addItem(f"... and {len(report['successful']) - 10} more")
            success_layout.addWidget(success_list)
            layout.addWidget(success_group)
        
        # Failed uploads list
        if report.get("failed"):
            failed_group = QGroupBox("Failed Uploads")
            failed_layout = QVBoxLayout(failed_group)
            failed_list = QListWidget()
            failed_list.setMaximumHeight(150)
            for item in report["failed"][:10]:
                item_text = f"✗ {item['design']} ({item['platform']}): {item.get('error', 'Unknown')}"
                failed_list.addItem(item_text)
            if len(report["failed"]) > 10:
                failed_list.addItem(f"... and {len(report['failed']) - 10} more")
            failed_layout.addWidget(failed_list)
            layout.addWidget(failed_group)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)


class PodProductCreatorPage(QWidget):
    """
    Main page for Automated Product Creation.
    Provides drag-and-drop interface, metadata configuration,
    and upload control for Redbubble, Spreadshirt, and Zazzle.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._designs = []
        self._platform_stats = {p: {"success": 0, "failed": 0} for p in ["Redbubble", "Spreadshirt", "Zazzle"]}
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        make_header(
            self, layout,
            "<h2>🎨 Automated Product Creation</h2>",
            "Create and upload products to Redbubble, Spreadshirt, and Zazzle automatically. "
            "Drag & drop your designs, configure metadata, and let the tool handle the rest.",
            title_style="color: #cba6f7;"
        )
        
        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Design import and list
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Configuration and controls
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setHandleWidth(4)
        
        layout.addWidget(splitter, 1)
        
        # Progress panel at bottom
        self._progress = ProgressPanel(show_log=True)
        self._progress.cancel_requested.connect(self._cancel_upload)
        layout.addWidget(self._progress)
    
    def _create_left_panel(self):
        """Create left panel with design import and list"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Import section
        import_group = QGroupBox("📁 Import Designs")
        import_layout = QVBoxLayout(import_group)
        import_layout.setSpacing(8)
        
        # Drag & drop area
        self._drop_zone = QFrame()
        self._drop_zone.setFixedHeight(100)
        self._drop_zone.setStyleSheet("""
            QFrame {
                background-color: #1e1e2e;
                border: 2px dashed #6c7086;
                border-radius: 8px;
            }
            QFrame:hover {
                border-color: #cba6f7;
                background-color: #252538;
            }
        """)
        self._drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        drop_label = QLabel("📤 Drag & Drop Images Here\nor click to browse")
        drop_label.setStyleSheet("color: #a6adc8; font-size: 13px;")
        drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_zone_layout = QVBoxLayout(self._drop_zone)
        self._drop_zone_layout.addWidget(drop_label)
        self._drop_zone.mousePressEvent = lambda e: self._browse_files()
        
        import_layout.addWidget(self._drop_zone)
        
        # Add files button
        add_btn = QPushButton("➕ Add Files")
        add_btn.clicked.connect(self._browse_files)
        import_layout.addWidget(add_btn)
        
        layout.addWidget(import_group)
        
        # Design list
        list_group = QGroupBox(f"🖼️ Designs ({len(self._designs)})")
        self._list_group = list_group
        list_layout = QVBoxLayout(list_group)
        
        self._design_list = QListWidget()
        self._design_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e2e;
                border: 1px solid #313244;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #313244;
            }
            QListWidget::item:selected {
                background-color: #45475a;
            }
        """)
        list_layout.addWidget(self._design_list)
        
        # List controls
        list_controls = QHBoxLayout()
        
        remove_btn = QPushButton("🗑 Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        list_controls.addWidget(remove_btn)
        
        clear_btn = QPushButton("🗑 Clear All")
        clear_btn.clicked.connect(self._clear_all)
        list_controls.addWidget(clear_btn)
        
        list_controls.addStretch()
        list_layout.addLayout(list_controls)
        
        layout.addWidget(list_group, 1)
        
        return panel
    
    def _create_right_panel(self):
        """Create right panel with configuration and controls"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Platform selection
        platform_group = QGroupBox("🌐 Select Platforms")
        platform_layout = QVBoxLayout(platform_group)
        platform_layout.setSpacing(8)
        
        self._platform_checks = {}
        for platform in ["Redbubble", "Spreadshirt", "Zazzle"]:
            cb = QCheckBox(f"✓ {platform}")
            cb.setChecked(True)
            cb.setStyleSheet("color: #cdd6f4; font-size: 13px; spacing: 8px;")
            platform_layout.addWidget(cb)
            self._platform_checks[platform] = cb
        
        layout.addWidget(platform_group)
        
        # Metadata configuration
        meta_group = QGroupBox("📝 Product Metadata")
        meta_layout = QFormLayout(meta_group)
        meta_layout.setSpacing(8)
        
        # Title template
        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("e.g. Funny Cat Design")
        self._title_input.returnPressed.connect(self._generate_tags_from_title)
        meta_layout.addRow("Title:", self._title_input)
        
        # Tags
        self._tags_input = QLineEdit()
        self._tags_input.setPlaceholderText("Comma-separated tags")
        meta_layout.addRow("Tags:", self._tags_input)
        
        auto_tags_btn = QPushButton("✨ Auto-Generate Tags")
        auto_tags_btn.clicked.connect(self._generate_tags_from_title)
        meta_layout.addRow("", auto_tags_btn)
        
        # Description
        self._desc_input = QTextEdit()
        self._desc_input.setPlaceholderText("Product description...")
        self._desc_input.setMaximumHeight(80)
        meta_layout.addRow("Description:", self._desc_input)
        
        layout.addWidget(meta_group)
        
        # Copy function
        copy_group = QGroupBox("📋 Quick Actions")
        copy_layout = QVBoxLayout(copy_group)
        copy_layout.setSpacing(8)
        
        copy_btn = QPushButton("📋 Copy Settings from Previous")
        copy_btn.clicked.connect(self._copy_previous_settings)
        copy_layout.addWidget(copy_btn)
        
        layout.addWidget(copy_group)
        
        # Upload controls
        control_group = QGroupBox("🚀 Upload Control")
        control_layout = QVBoxLayout(control_group)
        control_layout.setSpacing(8)
        
        # Start button
        self._start_btn = QPushButton("▶ Start Upload")
        self._start_btn.setProperty("class", "btn-primary")
        self._start_btn.clicked.connect(self._start_upload)
        control_layout.addWidget(self._start_btn)
        
        # Control buttons (initially disabled)
        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)
        
        self._pause_btn = QPushButton("⏸ Pause")
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self._pause_upload)
        controls_row.addWidget(self._pause_btn)
        
        self._resume_btn = QPushButton("▶ Resume")
        self._resume_btn.setEnabled(False)
        self._resume_btn.clicked.connect(self._resume_upload)
        controls_row.addWidget(self._resume_btn)
        
        self._stop_btn = QPushButton("⏹ Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_upload)
        controls_row.addWidget(self._stop_btn)
        
        control_layout.addLayout(controls_row)
        
        layout.addWidget(control_group)
        
        # Platform status cards
        status_group = QGroupBox("📊 Platform Status")
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(8)
        
        self._platform_cards = {}
        for platform in ["Redbubble", "Spreadshirt", "Zazzle"]:
            card = PlatformStatusCard(platform)
            status_layout.addWidget(card)
            self._platform_cards[platform] = card
        
        layout.addWidget(status_group)
        
        layout.addStretch()
        
        return panel
    
    def _browse_files(self):
        """Open file browser to select design files"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Design Files",
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp);;All Files (*)"
        )
        
        if files:
            self._add_designs(files)
    
    def _add_designs(self, file_paths):
        """Add designs to the list"""
        for path in file_paths:
            if path not in self._designs:
                self._designs.append(path)
                
                # Create widget for design
                widget = DesignItemWidget(path)
                item = QListWidgetItem(self._design_list)
                item.setSizeHint(widget.sizeHint())
                self._design_list.addItem(item)
                self._design_list.setItemWidget(item, widget)
        
        # Update count
        self._list_group.setTitle(f"🖼️ Designs ({len(self._designs)})")
    
    def _remove_selected(self):
        """Remove selected designs"""
        selected_items = self._design_list.selectedItems()
        for item in selected_items:
            row = self._design_list.row(item)
            if 0 <= row < len(self._designs):
                self._designs.pop(row)
            self._design_list.takeItem(row)
        
        self._list_group.setTitle(f"🖼️ Designs ({len(self._designs)})")
    
    def _clear_all(self):
        """Clear all designs"""
        self._designs.clear()
        self._design_list.clear()
        self._list_group.setTitle(f"🖼️ Designs (0)")
    
    def _generate_tags_from_title(self):
        """Auto-generate tags from title"""
        title = self._title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "No Title", "Please enter a title first.")
            return
        
        tags = TagGenerator.generate_tags(title)
        self._tags_input.setText(", ".join(tags))
    
    def _copy_previous_settings(self):
        """Copy settings from previous upload (placeholder)"""
        # In a real implementation, this would load from history/archive
        QMessageBox.information(
            self,
            "Copy Settings",
            "Settings copied from last upload session."
        )
    
    def _get_metadata(self):
        """Get current metadata configuration"""
        title = self._title_input.text().strip()
        tags_text = self._tags_input.text().strip()
        tags = [t.strip() for t in tags_text.split(",") if t.strip()] if tags_text else []
        description = self._desc_input.toPlainText().strip()
        
        return {
            "title": title or "Untitled Design",
            "tags": tags,
            "description": description or "",
            "products": None  # Could be extended to support product selection
        }
    
    def _get_selected_platforms(self):
        """Get list of selected platforms"""
        return [p for p, cb in self._platform_checks.items() if cb.isChecked()]
    
    def _start_upload(self):
        """Start the upload process"""
        if not self._designs:
            QMessageBox.warning(self, "No Designs", "Please add at least one design.")
            return
        
        platforms = self._get_selected_platforms()
        if not platforms:
            QMessageBox.warning(self, "No Platforms", "Please select at least one platform.")
            return
        
        metadata = self._get_metadata()
        
        # Disable controls
        self._start_btn.setEnabled(False)
        self._pause_btn.setEnabled(True)
        self._resume_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        
        # Start worker
        self._progress.start()
        self._worker = PodProductCreatorWorker(self._designs, metadata, platforms)
        
        # Connect signals
        self._worker.status.connect(self._progress.set_status)
        self._worker.progress.connect(self._progress.set_progress)
        self._worker.log.connect(self._progress.set_status)
        self._worker.platform_progress.connect(self._update_platform_progress)
        self._worker.platform_status.connect(self._update_platform_status)
        self._worker.design_processed.connect(self._on_design_processed)
        self._worker.upload_complete.connect(self._on_upload_complete)
        self._worker.error.connect(self._on_worker_error)
        
        self._worker.start()
    
    def _pause_upload(self):
        """Pause the upload process"""
        if self._worker:
            self._worker.pause()
            self._pause_btn.setEnabled(False)
            self._resume_btn.setEnabled(True)
    
    def _resume_upload(self):
        """Resume the upload process"""
        if self._worker:
            self._worker.resume()
            self._pause_btn.setEnabled(True)
            self._resume_btn.setEnabled(False)
    
    def _stop_upload(self):
        """Stop the upload process"""
        if self._worker:
            self._worker.stop()
            self._pause_btn.setEnabled(False)
            self._resume_btn.setEnabled(False)
            self._stop_btn.setEnabled(False)
    
    def _cancel_upload(self):
        """Cancel the upload (alias for stop)"""
        self._stop_upload()
    
    def _update_platform_progress(self, platform, percentage):
        """Update progress for a specific platform"""
        if platform in self._platform_cards:
            self._platform_cards[platform].update_progress(percentage)
    
    def _update_platform_status(self, platform, status):
        """Update status for a specific platform"""
        if platform in self._platform_cards:
            self._platform_cards[platform].update_status(status)
    
    def _on_design_processed(self, result):
        """Handle individual design completion"""
        design_name = result.get("design", "")
        platforms = result.get("platforms", {})
        
        # Find and update the design widget
        for i in range(self._design_list.count()):
            item = self._design_list.item(i)
            widget = self._design_list.itemWidget(item)
            if isinstance(widget, DesignItemWidget):
                if os.path.basename(widget.design_path) == design_name:
                    # Update platform badges
                    all_success = True
                    for platform, plat_result in platforms.items():
                        success = plat_result.get("success", False)
                        widget.update_platform_status(platform, success)
                        if success:
                            self._platform_stats[platform]["success"] += 1
                        else:
                            self._platform_stats[platform]["failed"] += 1
                        all_success = all_success and success
                    
                    # Set overall status
                    if all_success:
                        widget.set_overall_status("Complete")
                    elif any(p.get("success") for p in platforms.values()):
                        widget.set_overall_status("Partial")
                    else:
                        widget.set_overall_status("Failed")
                    
                    break
        
        # Update platform counters
        for platform, stats in self._platform_stats.items():
            if platform in self._platform_cards:
                self._platform_cards[platform].update_counters(stats["success"], stats["failed"])
    
    def _on_upload_complete(self, report):
        """Handle upload completion"""
        self._progress.finish(f"✅ Upload complete: {len(report.get('successful', []))} successful")
        
        # Reset controls
        self._start_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._resume_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)
        
        # Show report dialog
        dialog = UploadReportDialog(report, self)
        dialog.exec()
        
        self._worker = None
    
    def _on_worker_error(self, error_msg):
        """Handle worker error"""
        self._progress.finish(f"❌ Error: {error_msg}")
        
        # Reset controls
        self._start_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._resume_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)
        
        self._worker = None
    
    def focus_search(self):
        """Focus the title input field"""
        self._title_input.setFocus()
