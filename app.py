import asyncio
import json
import os
import sys
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Liquor Bond Automation Dashboard")

# Ensure static directory exists
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

# Mount static files to serve the frontend UI
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def get_dashboard():
    """Serves the main dashboard page."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Dashboard HTML not found. Please build static/index.html first.</h1>")

@app.websocket("/ws/run")
async def websocket_run(websocket: WebSocket):
    await websocket.accept()
    print("🔌 Client connected to logs WebSocket.")
    
    running_process = None
    try:
        # 1. Receive execution configuration from frontend
        data = await websocket.receive_text()
        config = json.loads(data)
        
        script_type = config.get("script", "all") # "all", "imfl", "cs", "stock"
        
        # Determine the target script and directories
        project_root = os.path.dirname(os.path.abspath(__file__))
        scripts_dir = os.path.join(project_root, "scripts")
        
        if script_type == "all":
            script_path = os.path.join(scripts_dir, "run_all.py")
        elif script_type == "imfl":
            script_path = os.path.join(scripts_dir, "main_imfl.py")
        elif script_type == "cs":
            script_path = os.path.join(scripts_dir, "main_cs.py")
        elif script_type == "stock":
            script_path = os.path.join(scripts_dir, "main_stock.py")
        else:
            await websocket.send_text(f"❌ Error: Unknown script type '{script_type}'\n")
            await websocket.close()
            return
            
        if not os.path.exists(script_path):
            await websocket.send_text(f"❌ Error: Script not found at {script_path}\n")
            await websocket.close()
            return

        # 2. Build the command line arguments
        args_list = []
        
        # Headless toggle
        if not config.get("headless", True):
            args_list.append("--no-headless")
            
        # Boolean flags
        if config.get("auto", False):
            args_list.append("--auto")
        if config.get("yesterday", False):
            args_list.append("--yesterday")
        if config.get("daily", False):
            args_list.append("--daily")
        if config.get("no_telegram", False):
            args_list.append("--no-telegram")
            
        # Optional text inputs
        day_val = config.get("day", "").strip()
        if day_val:
            args_list.extend(["--day", day_val])
            
        start_date_val = config.get("start_date", "").strip()
        if start_date_val:
            args_list.extend(["--start_date", start_date_val])
            
        end_date_val = config.get("end_date", "").strip()
        if end_date_val:
            args_list.extend(["--end_date", end_date_val])

        # 3. Launch subprocess asynchronously
        python_exe = sys.executable
        cmd = [python_exe, script_path] + args_list
        
        await websocket.send_text(f"🛠️ Starting process: {' '.join(cmd)}\n")
        await websocket.send_text("═" * 60 + "\n")
        
        # Start async subprocess with piped stdout & stderr merged
        running_process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=project_root
        )
        
        # Stream logs in real-time
        while True:
            line = await running_process.stdout.readline()
            if not line:
                break
            decoded_line = line.decode("utf-8", errors="ignore")
            # Send log line to client
            await websocket.send_text(decoded_line)
            # Yield to other async tasks
            await asyncio.sleep(0.001)
            
        # Wait for the process to fully complete
        returncode = await running_process.wait()
        
        # Send execution summary
        await websocket.send_text("\n" + "═" * 60 + "\n")
        if returncode == 0:
            await websocket.send_text(f"🎉 SUCCESS: Process finished with exit code 0\n")
            await websocket.send_json({"status": "success", "code": 0})
        else:
            await websocket.send_text(f"❌ FAILURE: Process exited with code {returncode}\n")
            await websocket.send_json({"status": "failed", "code": returncode})
            
    except WebSocketDisconnect:
        print("🔌 Client disconnected from WebSocket.")
        if running_process:
            print("⚠️ Terminating active automation process...")
            try:
                running_process.terminate()
                # Wait briefly to let it clean up, force kill if it doesn't exit
                await asyncio.wait_for(running_process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                print("💥 Process did not terminate, sending SIGKILL...")
                try:
                    running_process.kill()
                    await running_process.wait()
                except:
                    pass
            except Exception as ex:
                print(f"Error terminating process: {ex}")
                
    except Exception as e:
        print(f"❌ Server Error during websocket session: {e}")
        try:
            await websocket.send_text(f"\n❌ Internal Server Error: {e}\n")
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    # Start server locally on port 8000
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
