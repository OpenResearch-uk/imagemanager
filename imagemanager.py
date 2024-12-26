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
        self.image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp')
        self.cache_file = 'image_cache.json'
        self.clipboard_caption = ""
        self.unsaved_captions = {}
        self.load_cache()

    def load_cache(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                self.cache = json.load(f)
        else:
            self.cache = {}

    def save_cache(self):
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f)

    def get_image_info(self, image_path):
        if image_path in self.cache:
            return self.cache[image_path]

        info = {}
        try:
            with Image.open(image_path) as img:
                info['size'] = img.size
                info['format'] = img.format
                info['mode'] = img.mode
                
                info['metadata'] = {}
                
                if hasattr(img, 'info'):
                    for key, value in img.info.items():
                        if isinstance(value, (str, int, float)):
                            info['metadata'][key] = str(value)

                if hasattr(img, '_getexif') and img._getexif():
                    exif = img._getexif()
                    for tag_id in exif:
                        tag = TAGS.get(tag_id, tag_id)
                        value = exif[tag_id]
                        if isinstance(value, bytes):
                            try:
                                value = value.decode()
                            except:
                                value = str(value)
                        info['metadata'][f'EXIF_{tag}'] = str(value)
                
                gen_info = {}
                for key, value in info['metadata'].items():
                    key_lower = key.lower()
                    if isinstance(value, str):
                        if any(term in key_lower or term in value.lower() for term in 
                            ['parameters', 'prompt', 'negative_prompt', 'seed', 'steps', 
                             'sampler', 'cfg_scale', 'model', 'scheduler', 
                             'stable_diffusion', 'checkpoint']):
                            gen_info[key] = value
                            
                        if 'parameters' in key_lower and '{' in value:
                            try:
                                params = json.loads(value)
                                for k, v in params.items():
                                    gen_info[k] = str(v)
                            except:
                                pass
                info['gen_info'] = gen_info

        except Exception as e:
            st.error(f"Error reading image {image_path}: {str(e)}")
            return None

        stat = os.stat(image_path)
        info['file_size'] = stat.st_size
        info['created'] = datetime.datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
        info['modified'] = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')

        caption_path = os.path.splitext(image_path)[0] + '.txt'
        if os.path.exists(caption_path):
            with open(caption_path, 'r', encoding='utf-8') as f:
                info['caption'] = f.read().strip()
        else:
            info['caption'] = ''

        self.cache[image_path] = info
        self.save_cache()
        return info

    def get_caption(self, image_path):
        if image_path in self.unsaved_captions:
            return self.unsaved_captions[image_path]
        info = self.get_image_info(image_path)
        return info.get('caption', '') if info else ''

    def set_unsaved_caption(self, image_path, caption):
        self.unsaved_captions[image_path] = caption

    def save_caption(self, image_path, caption):
        caption_path = os.path.splitext(image_path)[0] + '.txt'
        try:
            with open(caption_path, 'w', encoding='utf-8') as f:
                f.write(caption)
            
            if image_path in self.cache:
                self.cache[image_path]['caption'] = caption
                self.save_cache()
            return True
        except Exception as e:
            st.error(f"Error saving caption: {str(e)}")
            return False

    def save_unsaved_captions(self):
        saved = 0
        for img_path, caption in self.unsaved_captions.items():
            if self.save_caption(img_path, caption):
                saved += 1
        self.unsaved_captions.clear()
        return saved

    def process_selected_images(self, operation, selected_images, **kwargs):
        processed = 0
        for img_path in selected_images:
            try:
                if operation == "move":
                    dest_folder = kwargs.get("dest_folder")
                    if not dest_folder:
                        continue
                    new_path = os.path.join(dest_folder, os.path.basename(img_path))
                    shutil.move(img_path, new_path)
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
                    caption_path = os.path.splitext(img_path)[0] + '.txt'
                    if os.path.exists(caption_path):
                        shutil.copy2(caption_path, os.path.join(dest_folder, os.path.basename(caption_path)))
                    processed += 1
                
                elif operation == "delete":
                    os.remove(img_path)
                    caption_path = os.path.splitext(img_path)[0] + '.txt'
                    if os.path.exists(caption_path):
                        os.remove(caption_path)
                    processed += 1

            except Exception as e:
                st.error(f"Error processing {os.path.basename(img_path)}: {str(e)}")
                continue

        return processed

    def open_with_external_app(self, image_path, app_name):
        try:
            if platform.system() == 'Windows':
                os.startfile(image_path)
            elif platform.system() == 'Darwin':
                subprocess.run(['open', '-a', app_name, image_path])
            else:
                subprocess.run([app_name, image_path])
            return True
        except Exception as e:
            st.error(f"Error opening image with {app_name}: {str(e)}")
            return False

def main():
    st.set_page_config(page_title="Image Viewer & Manager", layout="wide")
    st.title("Image Viewer & Manager")

    if 'selected_image' not in st.session_state:
        st.session_state.selected_image = None
    if 'selected_images' not in st.session_state:
        st.session_state.selected_images = set()
    if 'current_index' not in st.session_state:
        st.session_state.current_index = 0

    manager = ImageManager()

    with st.sidebar:
        st.title("Settings")
        directory = st.text_input("Image Directory", value=".")
        search_query = st.text_input("Search in captions", "")
        sort_by = st.selectbox("Sort by", ["Name", "Date Modified", "Size"])
        show_exif = st.checkbox("Show Metadata", False)
        view_mode = st.radio("View Mode", ["Grid", "Single Image", "Batch Edit"])
        
        st.markdown("<br>" * 10, unsafe_allow_html=True)
        st.markdown(
            """
            <div style='position: fixed; bottom: 20px; left: 20px;'>
                <h2>OpenResearch</h2>
            </div>
            """,
            unsafe_allow_html=True
        )

    if not os.path.exists(directory):
        st.error("Directory does not exist!")
        return

    image_files = []
    for ext in manager.image_extensions:
        image_files.extend(glob.glob(os.path.join(directory, f"*{ext}")))

    if sort_by == "Name":
        image_files.sort()
    elif sort_by == "Date Modified":
        image_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    else:
        image_files.sort(key=lambda x: os.path.getsize(x), reverse=True)

    if search_query:
        filtered_files = []
        for img_path in image_files:
            info = manager.get_image_info(img_path)
            if info and search_query.lower() in info.get('caption', '').lower():
                filtered_files.append(img_path)
        image_files = filtered_files

    if len(st.session_state.selected_images) > 0:
        st.sidebar.header(f"Selected Images ({len(st.session_state.selected_images)})")
        
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

        st.sidebar.subheader("Caption Operations")
        manager.clipboard_caption = st.sidebar.text_area("Clipboard Caption", manager.clipboard_caption)
        caption_op = st.sidebar.selectbox("Operation", ["Set", "Append", "Prepend"])
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("Apply Caption"):
                for img_path in st.session_state.selected_images:
                    current = manager.get_caption(img_path)
                    if caption_op == "Set":
                        new_caption = manager.clipboard_caption
                    elif caption_op == "Append":
                        new_caption = current + manager.clipboard_caption
                    else:  # Prepend
                        new_caption = manager.clipboard_caption + current
                    manager.set_unsaved_caption(img_path, new_caption)
                st.success("Caption changes pending. Click Save to apply.")
        
        with col2:
            if st.button("Save Captions"):
                saved = manager.save_unsaved_captions()
                st.success(f"Saved captions for {saved} images")
        
        if st.button("Clear Captions"):
            for img_path in st.session_state.selected_images:
                manager.set_unsaved_caption(img_path, "")

        if st.sidebar.button("Delete Selected", type="primary"):
            if st.sidebar.checkbox("Confirm deletion"):
                processed = manager.process_selected_images("delete", st.session_state.selected_images)
                st.success(f"Deleted {processed} files")
                st.session_state.selected_images.clear()

    if view_mode == "Single Image" and image_files:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Navigation controls
            nav_col1, nav_col2, nav_col3 = st.columns([1, 3, 1])
            with nav_col1:
                if st.button("Previous"):
                    st.session_state.current_index = (st.session_state.current_index - 1) % len(image_files)
            with nav_col2:
                st.session_state.current_index = st.selectbox(
                    "Select Image",
                    range(len(image_files)),
                    format_func=lambda x: os.path.basename(image_files[x]),
                    index=st.session_state.current_index
                )
            with nav_col3:
                if st.button("Next"):
                    st.session_state.current_index = (st.session_state.current_index + 1) % len(image_files)
            
            st.session_state.selected_image = image_files[st.session_state.current_index]
            st.image(st.session_state.selected_image, use_container_width=True)
        
        with col2:
            info = manager.get_image_info(st.session_state.selected_image)
            if info:
                st.subheader("Caption Editor")
                caption = manager.get_caption(st.session_state.selected_image)
                new_caption = st.text_area("Edit Caption", caption, height=200)
                if new_caption != caption:
                    manager.set_unsaved_caption(st.session_state.selected_image, new_caption)
                
                if st.button("Save Caption"):
                    if manager.save_unsaved_captions():
                        st.success("Caption saved successfully!")
                
                st.subheader("Image Information")
                st.write(f"Size: {info['size'][0]} x {info['size'][1]}")
                st.write(f"File size: {info['file_size'] / 1024:.1f} KB")
                st.write(f"Modified: {info['modified']}")
                
                st.subheader("Open With")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Open in Krita"):
                        manager.open_with_external_app(st.session_state.selected_image, "krita")
                with col2:
                    if st.button("Open in GIMP"):
                        manager.open_with_external_app(st.session_state.selected_image, "gimp")
                
if show_exif:
                    st.subheader("Metadata")
                    if not info['metadata'] and not info['gen_info']:
                        st.info("No metadata found in this image file")
                    else:
                        if info['metadata']:
                            df = pd.DataFrame(list(info['metadata'].items()), 
                                            columns=['Property', 'Value'])
                            st.dataframe(df, hide_index=True)
                        if info['gen_info']:
                            st.subheader("Generation Info")
                            df_gen = pd.DataFrame(list(info['gen_info'].items()), 
                                                columns=['Property', 'Value'])
                            st.dataframe(df_gen, hide_index=True)

    elif view_mode == "Grid":
        cols = st.columns(3)
        for idx, image_path in enumerate(image_files):
            col = cols[idx % 3]
            with col:
                info = manager.get_image_info(image_path)
                if info:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.image(image_path, caption=os.path.basename(image_path), use_container_width=True)
                    with col2:
                        is_selected = st.checkbox("Select", key=f"select_{idx}", 
                                               value=image_path in st.session_state.selected_images)
                        if is_selected and image_path not in st.session_state.selected_images:
                            st.session_state.selected_images.add(image_path)
                        elif not is_selected and image_path in st.session_state.selected_images:
                            st.session_state.selected_images.discard(image_path)
                    
                    caption = manager.get_caption(image_path)
                    new_caption = st.text_area(
                        "Caption",
                        caption,
                        height=100,
                        key=f"caption_grid_{idx}"
                    )
                    
                    if new_caption != caption:
                        manager.set_unsaved_caption(image_path, new_caption)
                    
                    if st.button("Save Caption", key=f"save_{idx}"):
                        if manager.save_unsaved_captions():
                            st.success("Caption saved!")
                    
                    st.write(f"Size: {info['size']}")
                    st.write(f"Modified: {info['modified']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Open in Krita", key=f"krita_{idx}"):
                            manager.open_with_external_app(image_path, "krita")
                    with col2:
                        if st.button("Open in GIMP", key=f"gimp_{idx}"):
                            manager.open_with_external_app(image_path, "gimp")
                    
                    if show_exif and (info['metadata'] or info['gen_info']):
                        with st.expander("Show Metadata"):
                            if info['metadata']:
                                df = pd.DataFrame(list(info['metadata'].items()), 
                                                columns=['Property', 'Value'])
                                st.dataframe(df, hide_index=True)
                            if info['gen_info']:
                                st.subheader("Generation Info")
                                df_gen = pd.DataFrame(list(info['gen_info'].items()), 
                                                    columns=['Property', 'Value'])
                                st.dataframe(df_gen, hide_index=True)

if __name__ == "__main__":
    main()