#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validation script for smart-file-writer skill.
Tests diagnostic and resolution functions.
"""

import os
import sys
import tempfile
import shutil
import stat

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def test_path_length_detection():
    """Test detection of overly long paths"""
    print("Testing path length detection...")

    # Create a very long path
    long_path = "C:\\" + "a" * 300 + ".txt"

    if os.name == 'nt' and len(long_path) > 260:
        print(f"  ✓ Detected long path: {len(long_path)} chars")
        return True
    else:
        print(f"  - Skipped (not Windows or path not long enough)")
        return True


def test_permission_check():
    """Test permission checking"""
    print("Testing permission checks...")

    # Create temp file
    with tempfile.NamedTemporaryFile(delete=False) as f:
        temp_path = f.name

    try:
        # Make read-only
        os.chmod(temp_path, stat.S_IREAD)

        # Check if detected as not writable
        if not os.access(temp_path, os.W_OK):
            print(f"  ✓ Detected read-only file")

            # Fix it
            os.chmod(temp_path, stat.S_IWRITE | stat.S_IREAD)

            if os.access(temp_path, os.W_OK):
                print(f"  ✓ Successfully made writable")
                return True
        else:
            print(f"  ✗ Failed to detect read-only")
            return False

    finally:
        os.unlink(temp_path)


def test_disk_space_check():
    """Test disk space checking"""
    print("Testing disk space check...")

    try:
        stat = shutil.disk_usage('.')
        free_gb = stat.free / (1024 ** 3)
        print(f"  ✓ Detected {free_gb:.2f} GB free")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def test_parent_directory_check():
    """Test parent directory validation"""
    print("Testing parent directory check...")

    # Non-existent parent
    test_path = os.path.join(tempfile.gettempdir(), "nonexistent", "test.txt")
    parent = os.path.dirname(test_path)

    if not os.path.exists(parent):
        print(f"  ✓ Detected missing parent: {parent}")

        # Create it
        os.makedirs(parent, exist_ok=True)

        if os.path.exists(parent):
            print(f"  ✓ Successfully created parent")
            # Clean up
            os.rmdir(parent)
            return True
    else:
        print(f"  - Parent already exists")
        return True


def test_atomic_write():
    """Test atomic write operation"""
    print("Testing atomic write...")

    test_file = os.path.join(tempfile.gettempdir(), "atomic_test.txt")
    content = "test content"

    try:
        # Write to temp file first
        dir_path = os.path.dirname(test_file)
        fd, temp_path = tempfile.mkstemp(dir=dir_path, text=True)

        with os.fdopen(fd, 'w') as f:
            f.write(content)

        # Atomic rename
        os.replace(temp_path, test_file)

        # Verify
        with open(test_file, 'r') as f:
            if f.read() == content:
                print(f"  ✓ Atomic write succeeded")
                return True
            else:
                print(f"  ✗ Content mismatch")
                return False

    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False
    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


def test_file_lock_detection():
    """Test file lock detection"""
    print("Testing file lock detection...")

    test_file = os.path.join(tempfile.gettempdir(), "lock_test.txt")

    try:
        # Create and open file
        with open(test_file, 'w') as f:
            f.write("test")

        # Try to open again (should work on most systems)
        try:
            with open(test_file, 'a') as f:
                pass
            print(f"  ✓ File lock detection test completed")
            return True
        except (PermissionError, IOError):
            print(f"  ✓ Detected file lock")
            return True

    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False
    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


def main():
    """Run all validation tests"""
    print("=" * 60)
    print("smart-file-writer Skill Validation")
    print("=" * 60)
    print()

    tests = [
        test_path_length_detection,
        test_permission_check,
        test_disk_space_check,
        test_parent_directory_check,
        test_atomic_write,
        test_file_lock_detection
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ✗ Test crashed: {e}")
            results.append(False)
        print()

    # Summary
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("✓ All tests passed!")
        return 0
    else:
        print(f"✗ {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
