from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/proteins", tags=["proteins"])

_STATIC = Path(__file__).parent.parent / "static"


@router.get("/demo/file")
def get_demo_file() -> FileResponse:
    pdb = _STATIC / "1CRN.pdb"
    if not pdb.exists():
        raise HTTPException(status_code=404, detail="Demo file not found")
    return FileResponse(str(pdb), media_type="chemical/x-pdb", filename="1CRN.pdb")
