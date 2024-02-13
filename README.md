# PyRvwr_GPT
PyRvwr is a versatile document processing tool that combines PDF and image text extraction, NLP for text merging, Google Docs integration, and OpenAI's GPT for answering questions. It is ideal for professionals seeking efficient document analysis and insight generation.

To maximize the utility of `PyRvwr_GPT`, follow these comprehensive instructions 🚀:

1. **Setup and Dependencies** 🛠️: Ensure Python and all required libraries (PIL, Google Client API, PyMuPDF, Pytesseract, OpenAI, Textract, Sentence Transformers, etc.) are installed. Also, install Tesseract OCR and set up Google Cloud credentials.

2. **Running the Program** 🏃: Launch `PyRvwr_GPT` via the terminal, specifying files or directories:
   - For individual or multiple files: `python PyRvwr_GPT.py --files "path\to\file1" "path\to\file2"`
   - For processing a directory: `python PyRvwr_GPT.py --dirs "path\to\directory"`

3. **Interacting with the Program** 💬: Post-processing, use commands like 'QUOTE' for search, 'q'uit, 'u'rl, 'c'lipboard, 'cl'ear, 'n'ew, to navigate or perform actions within the app.

4. **Weekly Maintenance** 📅: Delete `token.pickle` weekly for a fresh session start. On the first run post-deletion, log in to Google when prompted for Drive Docs saving and management.

5. **Understanding Output and Actions** 📄: The program processes text from PDFs/images, asks GPT-based questions, creates Google Docs, and manages document archiving with intuitive sound cues for user actions.

Remember, `PyRvwr_GPT` is a powerful document analysis and interaction tool, perfect for researchers, professionals, and anyone looking for deep insights and efficient document handling. 📊🔍
