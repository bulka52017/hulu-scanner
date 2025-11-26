
# hulubulu

Hulubulu - a temporary scanner to look for shai-hulud infected npm packages on your machine.

## Overview

This repository contains two tools to help detect the Shai-Hulud malware infection:

### 1. Python Package Scanner (`scan-infected-npm-packages.py`)

This Python script scans your machine for infected npm packages listed in a CSV file. It checks:
- Local projects (node_modules, package-lock.json, yarn.lock, pnpm-lock.yaml)
- Global npm installs (npm root -g)
- nvm installations (~/.nvm/versions/node/*/lib/node_modules)
- npm cache (npm config get cache)
- Homebrew installed node modules:
   - "/usr/local/lib/node_modules" for Homebrew Apple Intel
   - "/opt/homebrew/lib/node_modules" for Homebrew Apple Silicon

Results are saved in a JSON report.

**Do note, when you run the script on macOS, the app that you are running it with (e.g. console, iterm) will ask whether
it can access the photo album, downloads, etc. For this scripts purpose it is safe.**

### 2. Sandworm String Scanner (`scan-for-sandworm.sh`)

This shell script performs a text-based search across your entire home directory for the strings "Shai-Hulud" or "Sha1-Hulud". It:
- Recursively searches all files in your home directory
- Uses case-insensitive matching
- Shows line numbers and filenames for any matches
- Excludes itself from search results

This is useful for detecting the malware strings in files that may not be npm packages.

## Usage

### Python Package Scanner

macOS:
```
python3 scan-infected-npm-packages.py
```

elsewhere:
```
python scan-infected-npm-packages.py
```

### Sandworm String Scanner

First, make it executable:
```bash
chmod +x scan-for-sandworm.sh
```

Then run it:
```bash
./scan-for-sandworm.sh
```

**Note:** This scan may take some time depending on the size of your home directory.
