import os
import sys
import subprocess

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    phase_tests_dir = os.path.join(root_dir, "tests", "phase-tests")
    
    if not os.path.exists(phase_tests_dir):
        print(f"Error: Directory {phase_tests_dir} not found.")
        sys.exit(1)
        
    test_files = [f for f in os.listdir(phase_tests_dir) if f.startswith("test_phase") and f.endswith(".py")]
    test_files.sort()
    
    if not test_files:
        print("No phase tests found!")
        sys.exit(1)

    print("=" * 60)
    print(f" Fitness Bridge AI - Test Runner")
    print("=" * 60)
    print(f"Found {len(test_files)} phase tests to execute in sequence.\\n")
    
    all_passed = True
    
    for test_file in test_files:
        test_path = os.path.join("tests", "phase-tests", test_file)
        print(f"\\n[{test_file}] Running...")
        
        # Run pytest on the specific file
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_path, "-v", "--disable-warnings"],
            cwd=root_dir,
            capture_output=False
        )
        
        if result.returncode != 0:
            print(f"\\n❌ FAILED: {test_file}")
            all_passed = False
            break # Stop on first phase failure
        else:
            print(f"✅ PASSED: {test_file}")
            
    print("\\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL PHASE TESTS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("💥 TEST SUITE FAILED. Stopping execution.")
        sys.exit(1)

if __name__ == "__main__":
    main()
