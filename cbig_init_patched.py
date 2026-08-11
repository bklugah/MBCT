from . import compute_overlap_with_atlases
from . import visualize_overlap_lib
from . import load_example
from . import visualize_report_lib
import os
os.environ["GIT_PYTHON_REFRESH"] = "quiet"
import gzip
import shutil

def concatenate_files(file_path, num_parts, output_file):
    with open(output_file, 'wb') as f_out:
        for part_number in range(1, num_parts + 1):
            input_file = f'{file_path}.part{part_number}'
            with open(input_file, 'rb') as f_in:
                shutil.copyfileobj(f_in, f_out)

def unzip_model(file_path):
    # Decompress the compressed model
    with gzip.open(file_path + ".gz", 'rb') as f_in:
        with open(file_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

def combine_model(data_space, num_parts):
    compressed_file = os.path.join(data_dir, 'spin_rotations', data_space, '1000_spin_permutations_state0.pkl.gz')
    out_file = compressed_file.replace('.gz', '')
    # If the reassembled/uncompressed model already exists, skip the work so
    # repeated launches (and read-only installs) don't redo it.
    if os.path.exists(out_file):
        return
    concatenate_files(compressed_file, num_parts, compressed_file)
    unzip_model(out_file)

data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

# --- Offline-safe data handling (patched for packaged/offline use) ----------
# The upstream package unconditionally opens `data` as a git repo and pulls
# from GitHub at import time, which crashes in a packaged app with no network
# (or when the bundled data has no .git folder). The reference data is shipped
# with the application, so we only attempt git operations opportunistically
# and never let a missing network or missing .git stop the import.
if not os.path.exists(data_dir):
    # First-run with no bundled data: try to download (needs internet).
    try:
        from git import Repo
        print("Downloading CBIG reference data...")
        Repo.clone_from(
            'https://github.com/rubykong/cbig_network_correspondence_data',
            data_dir)
    except Exception as e:
        print(f"⚠️ Could not download CBIG reference data: {e}")
else:
    # Data is present (the normal packaged case): optionally update if this is
    # a real git checkout AND the network is reachable, but never fail.
    try:
        from git import Repo
        if os.path.isdir(os.path.join(data_dir, '.git')):
            repo_dir = Repo(data_dir)
            repo_dir.remotes.origin.pull('master')
    except Exception:
        # Offline, no .git, or git not installed — use the bundled data as-is.
        pass

# Reassemble the split spin-rotation models from the (bundled) data.
try:
    combine_model('fs_LR_32k', 3)
    combine_model('fsaverage6', 5)
except Exception as e:
    print(f"⚠️ Could not prepare spin-rotation models: {e}")
