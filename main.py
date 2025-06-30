from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# templates 폴더 경로 설정
templates = Jinja2Templates(directory="template")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/html", response_class=HTMLResponse)
async def get_html(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})

# uvicorn으로 실행할 때만 서버 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
