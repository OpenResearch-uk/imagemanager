import streamlit as st
import os
import glob
from PIL import Image
import datetime
import subprocess
import platform
from pathlib import Path
import shutil
import json
from PIL.ExifTags import TAGS
import pandas as pd

class ImageManager:
    def __init__(self):
        self.clipboard_caption = ""
        self.image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp')
        self.cache_file = 'image_cache.json'
        self.load_cache()

    def load_cache(self):
        """Load cached image information from JSON file"""
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                self.cache = json.load(f)
        else:
            self.cache = {}

    def save_cache(self):
        """Save current cache to JSON file"""
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f)

    def get_image_info(self, image_path):
        """Get image metadata and caption"""
        if image_path in self.cache:
            return self.cache[image_path]

        info = {}
        try:
            with Image.open(image_path) as img:
                info['size'] = img.size
                info['format'] = img.format
                info['mode'] = img.mode
                
                # Extract EXIF data
                exif = {}
                if hasattr(img, '_getexif') and img._getexif():
                    for tag_id, value in img._getexif().items():
                        tag = TAGS.get(tag_id, tag_id)
                        exif[tag] = str(value)
                info['exif'] = exif

        except Exception as e:
            st.error(f"Error reading image {image_path}: {str(e)}")
            return None

        # Get file information
        stat = os.stat(image_path)
        info['file_size'] = stat.st_size
        info['created'] = datetime.datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
        info['modified'] = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')

        # Get caption if exists
        caption_path = os.path.splitext(image_path)[0] + '.txt'
        if os.path.exists(caption_path):
            with open(caption_path, 'r', encoding='utf-8') as f:
                info['caption'] = f.read().strip()
        else:
            info['caption'] = ''

        self.cache[image_path] = info
        self.save_cache()
        return info

    def save_caption(self, image_path, caption):
        """Save caption to a text file and update cache"""
        caption_path = os.path.splitext(image_path)[0] + '.txt'
        try:
            with open(caption_path, 'w', encoding='utf-8') as f:
                f.write(caption)
            
            # Update cache
            if image_path in self.cache:
                self.cache[image_path]['caption'] = caption
                self.save_cache()
            return True
        except Exception as e:
            st.error(f"Error saving caption: {str(e)}")
            return False

    def process_selected_images(self, operation, selected_images, **kwargs):
        """Process selected images with various operations"""
        processed = 0
        for img_path in selected_images:
            try:
                if operation == "move":
                    dest_folder = kwargs.get("dest_folder")
                    if not dest_folder:
                        continue
                    new_path = os.path.join(dest_folder, os.path.basename(img_path))
                    shutil.move(img_path, new_path)
                    # Move caption file if exists
                    caption_path = os.path.splitext(img_path)[0] + '.txt'
                    if os.path.exists(caption_path):
                        shutil.move(caption_path, os.path.join(dest_folder, os.path.basename(caption_path)))
                    processed += 1
                
                elif operation == "copy":
                    dest_folder = kwargs.get("dest_folder")
                    if not dest_folder:
                        continue
                    new_path = os.path.join(dest_folder, os.path.basename(img_path))
                    shutil.copy2(img_path, new_path)
                    # Copy caption file if exists
                    caption_path = os.path.splitext(img_path)[0] + '.txt'
                    if os.path.exists(caption_path):
                        shutil.copy2(caption_path, os.path.join(dest_folder, os.path.basename(caption_path)))
                    processed += 1
                
                elif operation == "delete":
                    os.remove(img_path)
                    # Delete caption file if exists
                    caption_path = os.path.splitext(img_path)[0] + '.txt'
                    if os.path.exists(caption_path):
                        os.remove(caption_path)
                    processed += 1
                
                elif operation == "clear_caption":
                    self.save_caption(img_path, "")
                    processed += 1
                
                elif operation == "insert_clipboard":
                    self.save_caption(img_path, self.clipboard_caption)
                    processed += 1

            except Exception as e:
                st.error(f"Error processing {os.path.basename(img_path)}: {str(e)}")
                continue

        return processed

    def open_with_external_app(self, image_path, app_name):
        """Open image with external application"""
        try:
            if platform.system() == 'Windows':
                os.startfile(image_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', '-a', app_name, image_path])
            else:  # Linux
                subprocess.run([app_name, image_path])
            return True
        except Exception as e:
            st.error(f"Error opening image with {app_name}: {str(e)}")
            return False

def main():
    st.set_page_config(page_title="Image Viewer & Manager", layout="wide")
    st.title("Image Viewer & Manager")

    # Initialize session state for selected image and selected images set
    if 'selected_image' not in st.session_state:
        st.session_state.selected_image = None
    if 'selected_images' not in st.session_state:
        st.session_state.selected_images = set()

    # Initialize image manager
    manager = ImageManager()

    # Selected images actions
    if len(st.session_state.selected_images) > 0:
        st.sidebar.header(f"Selected Images ({len(st.session_state.selected_images)})")
        
        # File operations
        st.sidebar.subheader("File Operations")
        dest_folder = st.sidebar.text_input("Destination Folder")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("Move to Folder") and dest_folder:
                if os.path.exists(dest_folder):
                    processed = manager.process_selected_images("move", st.session_state.selected_images, dest_folder=dest_folder)
                    st.success(f"Moved {processed} files to {dest_folder}")
                    st.session_state.selected_images.clear()
                else:
                    st.error("Destination folder does not exist!")
        
        with col2:
            if st.button("Copy to Folder") and dest_folder:
                if os.path.exists(dest_folder):
                    processed = manager.process_selected_images("copy", st.session_state.selected_images, dest_folder=dest_folder)
                    st.success(f"Copied {processed} files to {dest_folder}")
                else:
                    st.error("Destination folder does not exist!")
        
        # Caption operations
        st.sidebar.subheader("Caption Operations")
        manager.clipboard_caption = st.sidebar.text_area("Clipboard Caption", manager.clipboard_caption)
        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("Insert Caption"):
                processed = manager.process_selected_images("insert_clipboard", st.session_state.selected_images)
                st.success(f"Updated captions for {processed} images")
        
        with col2:
            if st.button("Clear Captions"):
                processed = manager.process_selected_images("clear_caption", st.session_state.selected_images)
                st.success(f"Cleared captions for {processed} images")
        
        # Delete operation
        if st.sidebar.button("Delete Selected", type="primary"):
            if st.sidebar.checkbox("Confirm deletion"):
                processed = manager.process_selected_images("delete", st.session_state.selected_images)
                st.success(f"Deleted {processed} files")
                st.session_state.selected_images.clear()

    # Sidebar - Directory selection and search
    with st.sidebar:
        st.header("Settings")
        directory = st.text_input("Image Directory", value=".")
        search_query = st.text_input("Search in captions", "")
        sort_by = st.selectbox("Sort by", ["Name", "Date Modified", "Size"])
        show_exif = st.checkbox("Show EXIF data", False)
        view_mode = st.radio("View Mode", ["Grid", "Single Image", "Batch Edit"])
        
        # Batch caption operations
        if view_mode == "Batch Edit":
            st.header("Batch Caption Operations")
            operation = st.selectbox(
                "Operation",
                ["Append Text", "Prepend Text", "Search and Replace"]
            )
            
            if operation in ["Append Text", "Prepend Text"]:
                text_to_add = st.text_input("Text to add:")
                apply_to = st.radio("Apply to:", ["All Images", "Selected Images", "Images with Existing Captions"])
                
                if st.button("Apply Batch Operation"):
                    processed = 0
                    for img_path in image_files:
                        info = manager.get_image_info(img_path)
                        if info is None:
                            continue
                            
                        should_process = False
                        if apply_to == "All Images":
                            should_process = True
                        elif apply_to == "Selected Images":
                            should_process = img_path in st.session_state.get('selected_images', set())
                        elif apply_to == "Images with Existing Captions":
                            should_process = bool(info.get('caption', '').strip())
                        
                        if should_process:
                            current_caption = info.get('caption', '')
                            new_caption = (text_to_add + current_caption) if operation == "Prepend Text" else (current_caption + text_to_add)
                            if manager.save_caption(img_path, new_caption):
                                processed += 1
                    
                    st.success(f"Successfully processed {processed} images!")
            
            elif operation == "Search and Replace":
                search_text = st.text_input("Search for:")
                replace_text = st.text_input("Replace with:")
                match_case = st.checkbox("Match case")
                apply_to = st.radio("Apply to:", ["All Images", "Selected Images", "Images with Existing Captions"])
                
                if st.button("Apply Search and Replace"):
                    processed = 0
                    for img_path in image_files:
                        info = manager.get_image_info(img_path)
                        if info is None:
                            continue
                            
                        should_process = False
                        if apply_to == "All Images":
                            should_process = True
                        elif apply_to == "Selected Images":
                            should_process = img_path in st.session_state.get('selected_images', set())
                        elif apply_to == "Images with Existing Captions":
                            should_process = bool(info.get('caption', '').strip())
                        
                        if should_process:
                            current_caption = info.get('caption', '')
                            if match_case:
                                new_caption = current_caption.replace(search_text, replace_text)
                            else:
                                new_caption = current_caption.replace(search_text.lower(), replace_text)
                            
                            if current_caption != new_caption and manager.save_caption(img_path, new_caption):
                                processed += 1
                    
                    st.success(f"Successfully processed {processed} images!")

    # Main content area
    if not os.path.exists(directory):
        st.error("Directory does not exist!")
        return

    # Get all images in directory
    image_files = []
    for ext in manager.image_extensions:
        image_files.extend(glob.glob(os.path.join(directory, f"*{ext}")))

    # Sort images
    if sort_by == "Name":
        image_files.sort()
    elif sort_by == "Date Modified":
        image_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    else:  # Size
        image_files.sort(key=lambda x: os.path.getsize(x), reverse=True)

    # Filter by search query
    if search_query:
        filtered_files = []
        for img_path in image_files:
            info = manager.get_image_info(img_path)
            if info and search_query.lower() in info.get('caption', '').lower():
                filtered_files.append(img_path)
        image_files = filtered_files

    if view_mode == "Single Image":
        # Single image view with caption editing
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Image selection
            selected_idx = st.selectbox(
                "Select Image",
                range(len(image_files)),
                format_func=lambda x: os.path.basename(image_files[x])
            )
            
            if selected_idx is not None:
                st.session_state.selected_image = image_files[selected_idx]
                
                # Display selected image
                st.image(st.session_state.selected_image, use_column_width=True)
        
        with col2:
            if st.session_state.selected_image:
                info = manager.get_image_info(st.session_state.selected_image)
                if info:
                    # Caption editing
                    st.subheader("Caption Editor")
                    new_caption = st.text_area(
                        "Edit Caption",
                        info.get('caption', ''),
                        height=200,
                        key=f"caption_edit_{selected_idx}"
                    )
                    
                    # Save caption button
                    if st.button("Save Caption"):
                        if manager.save_caption(st.session_state.selected_image, new_caption):
                            st.success("Caption saved successfully!")
                    
                    # Image information
                    st.subheader("Image Information")
                    st.write(f"Size: {info['size'][0]} x {info['size'][1]}")
                    st.write(f"File size: {info['file_size'] / 1024:.1f} KB")
                    st.write(f"Modified: {info['modified']}")
                    
                    # External application buttons
                    st.subheader("Open With")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Open in Krita"):
                            manager.open_with_external_app(st.session_state.selected_image, "krita")
                    with col2:
                        if st.button("Open in GIMP"):
                            manager.open_with_external_app(st.session_state.selected_image, "gimp")
                    
                    # EXIF data
                    if show_exif and info['exif']:
                        st.subheader("EXIF Data")
                        with st.expander("Show EXIF"):
                            for key, value in info['exif'].items():
                                st.write(f"{key}: {value}")

    elif view_mode == "Grid":
        # Grid view
        cols = st.columns(3)
        for idx, image_path in enumerate(image_files):
            col = cols[idx % 3]
            with col:
                info = manager.get_image_info(image_path)
                if info:
                    # Make image clickable and selectable
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        if st.image(image_path, caption=os.path.basename(image_path), use_container_width=True):
                            st.session_state.selected_image = image_path
                    with col2:
                        is_selected = st.checkbox("Select", key=f"select_{idx}", 
                                               value=image_path in st.session_state.selected_images)
                        if is_selected:
                            st.session_state.selected_images.add(image_path)
                        else:
                            st.session_state.selected_images.discard(image_path)
                    
                    # Caption with edit functionality
                    new_caption = st.text_area(
                        "Caption",
                        info.get('caption', ''),
                        height=100,
                        key=f"caption_grid_{idx}"
                    )
                    
                    if st.button("Save Caption", key=f"save_{idx}"):
                        if manager.save_caption(image_path, new_caption):
                            st.success("Caption saved!")
                    
                    # Basic info
                    st.write(f"Size: {info['size']}")
                    st.write(f"Modified: {info['modified']}")
                    
                    # Actions
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Open in Krita", key=f"krita_{idx}"):
                            manager.open_with_external_app(image_path, "krita")
                    with col2:
                        if st.button("Open in GIMP", key=f"gimp_{idx}"):
                            manager.open_with_external_app(image_path, "gimp")

if __name__ == "__main__":
    main()