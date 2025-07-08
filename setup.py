import os
import sys
import subprocess
import shutil

def run_command(command, description):
    print(f"{description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"{description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"{description} failed: {e.stderr}")
        return False

def main():
    print("=" * 60)
    print("Robo Calling AI Agent - Setup")
    print("=" * 60)
    
    print("\n1. Checking Python version...")
    if sys.version_info < (3, 11):
        print("Python 3.11+ required")
        return False
    print(f"Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    print("\n2. Creating directories...")
    directories = ['data', 'logs', 'data/uploads']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"   Created: {directory}")
    print("Directories created")
    
    print("\n3. Installing dependencies...")
    if not run_command("pip install -r requirements.txt", "Installing Python packages"):
        return False
    
    print("\n4. Setting up environment...")
    if not os.path.exists('.env'):
        if os.path.exists('.env.example'):
            shutil.copy('.env.example', '.env')
            print("Environment file created (.env)")
            print("Please edit .env file with your Twilio credentials")
        else:
            print(".env.example not found")
            return False
    else:
        print("Environment file already exists")
    
    print("\n5. Running demo...")
    if not run_command("python demo.py", "Running demo script"):
        print("Demo failed, but setup may still be successful")
    
    print("\n" + "=" * 60)
    print("Setup completed!")
    print("=" * 60)
    print("\nNext Steps:")
    print("1. Edit .env file with your Twilio credentials")
    print("2. Run: python src/app.py")
    print("3. Open: http://localhost:5000")
    print("4. Upload contacts and start calling!")
    print("\nDocumentation: README.md")
    print("Demo: python demo.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

