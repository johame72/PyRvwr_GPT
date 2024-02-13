import os
import winsound
import re
import shutil
import pickle
import argparse
from datetime import datetime
from PIL import Image
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import fitz #PyMuPDF
import pytesseract
import PyPDF2
import openai
import textract
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import pyperclip


# Define a constant for the context window size
CONTEXT_WINDOW_SIZE = 2200

# Maximum number of tokens that can be handled by the model
MAX_TOKENS = 8192

# If modifying these SCOPES, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def merge_texts_nlp(text1, text2, similarity_threshold=0.8):
    """
    Merge two strings intelligently using NLP. This function converts sentences into embeddings,
    and then combines them based on semantic similarity.
    """
    model = SentenceTransformer('all-MiniLM-L6-v2')  # You can choose the model according to your requirement

    # Split the texts into sentences
    sentences1 = text1.split('. ')
    sentences2 = text2.split('. ')

    # Calculate embeddings for each sentence
    embeddings1 = model.encode(sentences1, convert_to_tensor=True)
    embeddings2 = model.encode(sentences2, convert_to_tensor=True)

    # Calculate similarity matrix
    similarity_matrix = cosine_similarity(embeddings1, embeddings2)

    # Combine sentences, excluding those that are too similar
    merged_sentences = sentences1.copy()
    for i, sentence2 in enumerate(sentences2):
        if max(similarity_matrix[:, i]) < similarity_threshold:
            merged_sentences.append(sentence2)

    return '. '.join(merged_sentences)

class Document:
    """A class for handling different types of documents."""

    def __init__(self, file_path):
        self.file_path = file_path
        self.text = None

    def extract_text_from_image(self, img):
        return pytesseract.image_to_string(img)

    def extract_text_from_pdf_pypdf2(self):
        text = ""
        with open(self.file_path, "rb") as file:
            pdf_reader = PyPDF2.PdfFileReader(file)
            for page_number in range(pdf_reader.numPages):
                page = pdf_reader.getPage(page_number)
                text += page.extract_text()
        return text

    def extract_text_from_pdf_pymupdf(self):
        doc = fitz.open(self.file_path)
        text = ""
        for page in doc:
            text += page.get_text("text")
            image_list = page.get_images(full=True)
            for img in image_list:
                ...
        return text

    def extract_text_from_pdf(self):
        doc = fitz.open(self.file_path)
        text = ""
        for page in doc:
            text += page.get_text("text")
            image_list = page.get_images(full=True)
            for img in image_list:
                xref = img[0]
                base = img[1]
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha < 4:  # this is GRAY or RGB
                    pix.save(f"temp_{base}.png")
                else:  # CMYK: convert to RGB first
                    pix1 = fitz.Pixmap(fitz.csRGB, pix)
                    pix1.save(f"temp_{base}.png")
                    pix1 = None  # free Pixmap resources

                img = Image.open(f"temp_{base}.png")
                text += self.extract_text_from_image(img)
                os.remove(f"temp_{base}.png")  # remove temp image file
        return text

    def extract_text(self):
        _, file_extension = os.path.splitext(self.file_path)
        if file_extension.lower() == '.pdf':
            text_pymupdf = self.extract_text_from_pdf_pymupdf()
            text_pypdf2 = self.extract_text_from_pdf_pypdf2()
            text_pdf = self.extract_text_from_pdf()
            self.text = merge_texts_nlp(text_pymupdf, text_pypdf2)
            self.text = merge_texts_nlp(self.text, text_pdf)
        else:
            try:
                self.text = textract.process(self.file_path).decode('utf-8')
            except Exception as e:
                print(f"Failed to extract text from file {self.file_path}: {e}")
                self.text = ""
        return self.text

class QuestionAsker:
    """A class to ask questions to OpenAI's GPT-4 model."""

    def __init__(self, model):
        self.model = model
        self.messages = []

    def ask_question(self, question, temperature=0.01):
        try:
            self.messages.append({"role": "user", "content": question})

            while len('\n'.join([message["content"] for message in self.messages])) > MAX_TOKENS:
                del self.messages[0]

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=self.messages,
                temperature=temperature,
                top_p=0.25,
                frequency_penalty=0.2,
                presence_penalty=.2
            )

            self.messages.append({"role": "assistant", "content": response['choices'][0]['message']['content']})

            return response['choices'][0]['message']['content']
        except Exception as e:
            print(f"Failed to generate answer: {e}")
            return ""


class GoogleDocCreator:
    """A class to create Google Docs."""

    def __init__(self):
        self.file_id = None
        self.creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                self.creds = pickle.load(token)
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                self.creds = flow.run_local_server(port=0)
            with open('token.pickle', 'wb') as token:
                pickle.dump(self.creds, token)

    def create(self, filename):
        """Create a new Google Doc."""
        try:
            service = build('drive', 'v3', credentials=self.creds)
            file_metadata = {
                'name': filename,
                'mimeType': 'application/vnd.google-apps.document'
            }
            media = MediaFileUpload(filename, 
                                    mimetype='text/plain',
                                    resumable=True)
            file = service.files().create(body=file_metadata,
                                          media_body=media,
                                          fields='id').execute()
            self.file_id = file.get('id')
        except Exception as e:
            print(f"An error occurred: {e}")

    def archive_and_create_new_doc(self):
        archive_folder = "CONTENT_ARCHIVE"
        current_file_path = 'output.txt'
        prefix = ''

        # Read the first 10 lines of the file
        with open(current_file_path, 'r') as f:
            for _ in range(10):
                line = f.readline().strip()  # strip() is used to remove leading/trailing whitespace (including newlines)
                if line:
                    # Remove spaces
                    no_spaces = line.replace(" ", "")
                    # Check if the line is not empty after removing spaces
                    if no_spaces:
                        # Get the first 16 characters from the non-empty line
                        prefix = no_spaces[:16]
                        break

        # If we didn't find a non-empty line, use the current datetime as a prefix
        if not prefix:
            prefix = datetime.now().strftime('%Y%m%dT%H%M%S')
        else:
            # Ensure the prefix is a valid filename
            invalid_chars = '<>:"/\\|?*\n'
            for char in invalid_chars:
                prefix = prefix.replace(char, '')

        new_file_path = os.path.join(archive_folder, f"{prefix}_content.txt")

        # Create the archive folder if it doesn't exist
        if not os.path.exists(archive_folder):
            os.makedirs(archive_folder)

        # Move the current content file to the archive folder with the prefix
        shutil.move(current_file_path, new_file_path)

        print(f"Archived as: {new_file_path}")

        # Upload the archived file to Google Drive
        self.create(new_file_path)

        # Create a new content file
        open(current_file_path, 'a').close()


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Answer questions based on document content.')
    parser.add_argument('--files', type=str, nargs='*', help='Full paths to files')
    parser.add_argument('--dirs', type=str, nargs='*', help='Full paths to directories containing files')
    args = parser.parse_args()

    # Load the file(s) and extract text
    text = ""
    if args.files is not None:
        for file_path in args.files:
            print(f"Processing file: {file_path}")
            doc = Document(file_path)
            text += doc.extract_text()

    if args.dirs is not None:
        for dir_path in args.dirs:
            if os.path.isdir(dir_path):
                file_names = os.listdir(dir_path)
                for file_name in file_names:
                    file_path = os.path.join(dir_path, file_name)
                    print(f"Processing file: {file_path}")
                    doc = Document(file_path)
                    text += doc.extract_text()

    # Set OpenAI API key
    openai.api_key = os.getenv('OPENAI_API_KEY')

    # Initialize the QuestionAsker
    asker = QuestionAsker("gpt-4-0613")  # Replace 'gpt-4' with the model you're using

    # Initialize the GoogleDocCreator
    doc_creator = GoogleDocCreator()

    # Initialize the last_response variable
    last_response = ""

    sound_file_path = r"C:\Windows\WinSxS\amd64_microsoft-windows-shell-sounds_31bf3856ad364e35_10.0.22621.1_none_78a847e6a947c766\Windows Message Nudge.wav"
    
    while True:
        winsound.PlaySound(sound_file_path, winsound.SND_FILENAME)
        # Get user question
        question = input("\nNext question? 'QUOTE' for search, 'q'uit, 'u'rl, 'c'lipboard, 'cl'ear, 'n'ew: ")
        if question.lower() == 'q':
            break
        elif question.lower() == 'u':
            print(f'The Google Doc can be accessed at: https://docs.google.com/document/d/{doc_creator.file_id}/edit')
        elif question.lower() == 'c':
            pyperclip.copy(last_response)
            print('Last response copied to clipboard.')
        elif question.lower() == 'cl':
            asker.messages = []
            print('Context and previous answers cleared.')
        elif question.lower() == 'n':
            doc_creator.archive_and_create_new_doc()
            doc_creator.create('output.txt')  # update Google Doc to new 'output.txt'
        else:
            # Check if there are quoted words/phrases in the question
            search_terms = re.findall(r"'(.*?)'", question)

            # Use the quoted terms to provide additional context
            additional_context = ""
            for term in search_terms:
                start = text.find(term)
                if start != -1:
                    # Extract some context around the found term
                    context_start = max(0, start - CONTEXT_WINDOW_SIZE // 2)
                    context_end = min(len(text), start + len(term) + CONTEXT_WINDOW_SIZE // 2)
                    additional_context += text[context_start:context_end]

            # Determine the context for the question
            context_start = max(0, text.find(question) - CONTEXT_WINDOW_SIZE // 2)
            context_end = min(len(text), context_start + CONTEXT_WINDOW_SIZE)
            context = text[context_start:context_end]

            # Combine the original context and additional context from quoted terms
            full_context = context + "\n" + additional_context

            # Add the context to the messages
            asker.messages.append({"role": "system", "content": f"Context: {full_context}"})

            # Ask the question
            answer = asker.ask_question(question)

            # Update the last_response variable
            last_response = answer

            # Print the answer
            print(f"\nAnswer: {answer}")

            # Append the question and answer to a text file
            with open('output.txt', 'a') as f:
                # Check if the file is not new (not empty)
                if os.stat('output.txt').st_size != 0:
                    # Add two new lines
                    f.write('\n\n')
                # Add the date-time stamp and the Python program filename on the same line
                f.write(datetime.now().strftime('%Y%m%dT%H%M%S') + ' | Python Program Filename: ' + os.path.basename(__file__) + '\n')
                # Add the referenced document
                f.write('Referenced Document: ' + file_path + '\n')
                # Add one new line
                f.write('\n')
                f.write(f"Question: {question}\n")
                # Add one new line
                f.write('\n')
                f.write("Answer:\n")
                f.write(f"{answer}\n")

            # Create a Google Doc with the responses
            doc_creator.create('output.txt')

        # Play sound at the end of each loop
        winsound.PlaySound(sound_file_path, winsound.SND_FILENAME)


if __name__ == "__main__":
    main()
