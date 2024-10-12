# Langhub POC

## Get Started

Make .env file in root and add 
```bash
OPENAI=OPENAI_API_KEY
PINECONE=PINECONE_API_KEY
CLIENT_ID=AWS_CLIENT_ID
CLIENT_SECRET=AWS_CLIENT_SECRET
REDIRECT_URI=http://localhost:8000/login/callback
```

### Backend

```bash
pip install -r requirements.txt
cd app
fastapi dev
```


### Frontend

```bash
cd frontend
npm install
npm start
```