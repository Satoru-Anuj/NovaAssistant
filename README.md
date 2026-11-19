NovaAssistant
==============================

A Python-powered desktop AI assistant for Windows.

NovaAssistant is a personal desktop assistant designed to bring voice interaction, AI-powered responses, and desktop productivity tools together in one application.

Built with Python, NovaAssistant focuses on lightweight performance, a modern interface, and practical everyday assistance.

FEATURES
--------

• Voice interaction – interact with Nova using voice commands.
• AI-powered responses – uses the Groq API for AI-generated responses.
• Voice authentication – local speaker verification.
• Modern desktop interface – custom floating assistant with animated visual states.
• Nova Studio – AI-assisted creative and editing tools.
• Video editing tools – video editing and preview modules.
• Customisation – modular scripts for interface improvements.
• Windows integration – designed for Windows desktop use.

Some features and modules are still under development.

TECHNOLOGY STACK
----------------

Python 3.12 – Core application
PySide6 – Desktop interface
Tkinter – Additional interface components
Groq API – AI responses
SpeechRecognition – Voice input
PyAudio – Microphone input
pyttsx3 – Text-to-speech
SpeechBrain – Speaker verification

PROJECT STRUCTURE
-----------------

NovaAssistant/
|
|-- main.py
|-- nova_widget.py
|-- nova_app.py
|-- nova_studio.py
|-- nova_studio_qt.py
|-- nova_ai_editor.py
|-- nova_video_editor.py
|-- nova_voice_auth.py
|
|-- Run-Nova.ps1
|-- requirements.txt
|-- requirements-full.txt
|-- .gitignore
|
|-- ui/
|   |-- app.js
|   |-- index.html
|   |-- style.css
|
|-- Additional development and patch scripts

REQUIREMENTS
------------

• Windows 10 or later
• Python 3.12
• Microphone for voice interaction
• Internet connection for Groq API functionality
• Groq API key

INSTALLATION
------------

1. Clone the repository:

git clone https://github.com/Satoru-Anuj/NovaAssistant.git

2. Open the project folder:

cd NovaAssistant

3. Create a virtual environment:

python -m venv .venv

4. Activate the environment:

.\.venv\Scripts\Activate.ps1

5. Install dependencies:

python -m pip install -r requirements.txt

CONFIGURATION
-------------

Create a file named .env in the project root directory.

Add the following configuration:

GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b

Replace the placeholder with your own API key.

IMPORTANT: Never upload your .env file, API keys, passwords, or private voice profile to GitHub.

RUNNING NOVAASSISTANT
--------------------

Run the PowerShell launcher:

.\Run-Nova.ps1

Individual application modules can also be launched using Python.

DEVELOPMENT GOALS
-----------------

• Improve voice recognition and response quality.
• Develop a more responsive animated interface.
• Expand desktop productivity features.
• Improve AI-assisted editing tools.
• Optimise performance for lower-end computers.
• Improve application reliability and modularity.

REPOSITORY
----------

GitHub:
https://github.com/Satoru-Anuj/NovaAssistant

LICENSE
-------

No open-source license has been specified yet. All rights reserved by the repository owner unless a license is added.

NovaAssistant – Your desktop, your assistant.
