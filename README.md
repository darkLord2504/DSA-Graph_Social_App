# Bubble

Bubble is a social network app built with Flask. It demonstrates:

- An intro page with an animated Enter button.
- A user list with profile pictures.
- A user account page featuring:
  - Profile summary with followers/following dropdowns (with profile pics and action buttons).
  - A chat list and a conversation area loaded on the same page.
  - Profile picture upload.
- An admin dashboard displaying a network graph visualization with proper directed/undirected edges and block arrows.
- A consistent color theme (white, baby blue, turquoise).

## Setup

1. Create a virtual environment:
python -m venv venv

2. Activate the virtual environment:
- On Windows: `venv\Scripts\activate`
- On Mac/Linux: `source venv/bin/activate`

3. Install dependencies:
pip install -r requirements.txt

4. Run the application:
python run.py