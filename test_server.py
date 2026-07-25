import uvicorn

def test_server():
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000)

if __name__ == "__main__":
    test_server()
