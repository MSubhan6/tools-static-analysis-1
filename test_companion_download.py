#!/usr/bin/env python3
"""Test the Windows-friendly companion server download flow."""

import requests
import zipfile
import io
import os
import subprocess
import time
import signal
import sys
from pathlib import Path

# Test configuration
MCP_SERVER_PORT = 8080
DOWNLOAD_URL = f"http://localhost:{MCP_SERVER_PORT}/companion/download"
TEST_EXTRACT_DIR = Path("/tmp/test-companion-extract")

def start_mcp_server():
    """Start MCP server in HTTP mode."""
    print("🚀 Starting MCP server in HTTP mode...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "static_analysis_mcp.server", "--http", str(MCP_SERVER_PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent
    )

    # Wait for server to be ready (try downloading from companion endpoint)
    for i in range(30):
        try:
            # Try a simple GET request to see if server is responding
            response = requests.get(f"http://localhost:{MCP_SERVER_PORT}/companion/download", timeout=1)
            if response.status_code in [200, 404, 500]:  # Any response means server is up
                print(f"✓ MCP server started on port {MCP_SERVER_PORT}")
                time.sleep(2)  # Give it a moment to fully initialize
                return proc
        except requests.exceptions.RequestException:
            time.sleep(1)

    proc.kill()
    raise RuntimeError("Failed to start MCP server")

def test_download():
    """Test downloading the companion server ZIP."""
    print(f"\n📥 Testing download from {DOWNLOAD_URL}...")

    response = requests.get(DOWNLOAD_URL, timeout=10)

    # Verify response
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    print("✓ Download endpoint returned 200 OK")

    # Verify content type
    content_type = response.headers.get('Content-Type', '')
    assert 'application/zip' in content_type, f"Expected application/zip, got {content_type}"
    print(f"✓ Content-Type is {content_type}")

    # Verify Content-Disposition header
    content_disposition = response.headers.get('Content-Disposition', '')
    assert 'companion-server.zip' in content_disposition, f"Expected companion-server.zip in header, got {content_disposition}"
    print(f"✓ Content-Disposition: {content_disposition}")

    # Verify it's a valid ZIP
    zip_data = response.content
    assert len(zip_data) > 0, "Downloaded file is empty"
    print(f"✓ Downloaded {len(zip_data)} bytes")

    return zip_data

def test_extract_and_verify(zip_data):
    """Extract ZIP and verify contents."""
    print(f"\n📦 Extracting ZIP to {TEST_EXTRACT_DIR}...")

    # Clean up previous test
    if TEST_EXTRACT_DIR.exists():
        import shutil
        shutil.rmtree(TEST_EXTRACT_DIR)
    TEST_EXTRACT_DIR.mkdir(parents=True)

    # Extract ZIP
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        zf.extractall(TEST_EXTRACT_DIR)
        file_list = zf.namelist()
        print(f"✓ Extracted {len(file_list)} files:")
        for name in file_list:
            print(f"  - {name}")

    # Verify expected files exist
    expected_files = [
        'companion/package.json',
        'companion/server.js',
        'companion/fix-workflow.js'
    ]

    print("\n🔍 Verifying expected files...")
    for expected in expected_files:
        file_path = TEST_EXTRACT_DIR / expected
        assert file_path.exists(), f"Expected file not found: {expected}"
        file_size = file_path.stat().st_size
        print(f"✓ {expected} ({file_size} bytes)")

    # Verify bash scripts are NOT included
    print("\n🚫 Verifying bash scripts are excluded...")
    bash_scripts = ['companion-cli.sh', 'install-companion.sh']
    for script in bash_scripts:
        assert script not in file_list, f"Bash script should not be in ZIP: {script}"
        print(f"✓ {script} correctly excluded")

    return TEST_EXTRACT_DIR / 'companion'

def test_companion_startup(companion_dir):
    """Test that the companion server can start from extracted files."""
    print(f"\n🎯 Testing companion server startup from {companion_dir}...")

    # Verify package.json exists and has npm start script
    package_json = companion_dir / 'package.json'
    import json
    with open(package_json) as f:
        pkg = json.load(f)

    assert 'scripts' in pkg, "package.json missing scripts"
    assert 'start' in pkg['scripts'], "package.json missing 'start' script"
    print(f"✓ package.json has 'start' script: {pkg['scripts']['start']}")

    # Start companion server (using node directly, not npm)
    print("✓ Starting companion server...")
    proc = subprocess.Popen(
        ['node', 'server.js', '--port', '19280'],
        cwd=companion_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to start
    companion_started = False
    for i in range(10):
        try:
            response = requests.get('http://localhost:19280/_ping', timeout=1)
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Companion server started successfully")
                print(f"✓ Health check response: {data}")
                companion_started = True
                break
        except requests.exceptions.RequestException:
            time.sleep(1)

    # Stop companion server
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    assert companion_started, "Companion server failed to start"
    print("✓ Companion server stopped cleanly")

def cleanup(mcp_proc):
    """Clean up test resources."""
    print("\n🧹 Cleaning up...")

    if mcp_proc:
        mcp_proc.terminate()
        try:
            mcp_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            mcp_proc.kill()
        print("✓ MCP server stopped")

    if TEST_EXTRACT_DIR.exists():
        import shutil
        shutil.rmtree(TEST_EXTRACT_DIR)
        print(f"✓ Cleaned up {TEST_EXTRACT_DIR}")

def main():
    """Run all tests."""
    mcp_proc = None

    try:
        print("=" * 70)
        print("Windows-Friendly Companion Server Download Flow Test")
        print("=" * 70)

        # Start MCP server
        mcp_proc = start_mcp_server()

        # Test download
        zip_data = test_download()

        # Test extraction and verification
        companion_dir = test_extract_and_verify(zip_data)

        # Test companion startup
        test_companion_startup(companion_dir)

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print("\nVerified:")
        print("  ✓ Download endpoint serves ZIP file")
        print("  ✓ ZIP contains correct files (package.json, server.js, fix-workflow.js)")
        print("  ✓ ZIP excludes bash scripts")
        print("  ✓ Extracted companion server starts successfully")
        print("  ✓ Health check endpoint works")
        print("\nThe Windows-friendly download flow is working correctly!")

        return 0

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        cleanup(mcp_proc)

if __name__ == '__main__':
    sys.exit(main())
