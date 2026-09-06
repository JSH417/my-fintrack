import os
import sys
import time
import webbrowser
import threading
import socket

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def open_browser(url):
    time.sleep(1.2)
    print(f"\n[FinTrack] 웹 브라우저를 실행합니다: {url}")
    webbrowser.open(url)

def main():
    # profile query parameter from argument e.g. python run.py --profile mom
    profile = "mom"
    for i, arg in enumerate(sys.argv):
        if arg == "--profile" and i + 1 < len(sys.argv):
            profile = sys.argv[i + 1]

    port = 8000
    host = "0.0.0.0" # 외부(스마트폰) 접속 허용
    local_ip = get_local_ip()

    url_local = f"http://localhost:{port}/?profile={profile}"
    url_mobile = f"http://{local_ip}:{port}/?profile={profile}"

    print("=" * 65)
    print(f"  [FinTrack] 행복 가계부 ({'어머니 모드' if profile == 'mom' else '내 가계부/투자 모드'})")
    print("=" * 65)
    print(f"  · PC 접속 주소   : {url_local}")
    print(f"  · 휴대폰 접속 주소: {url_mobile} (같은 Wi-Fi)")
    print("=" * 65)
    print("  서버를 종료하려면 이 창에서 Ctrl + C 를 누르세요.\n")

    threading.Thread(target=open_browser, args=(url_local,), daemon=True).start()

    try:
        import uvicorn
        uvicorn.run("backend.main:app", host=host, port=port, reload=False, log_level="info")
    except KeyboardInterrupt:
        print("\nFinTrack 프로그램을 정상적으로 종료했습니다.")
    except Exception as e:
        print(f"\n실행 중 오류가 발생했습니다: {e}")
        input("엔터 키를 누르면 종료합니다...")

if __name__ == "__main__":
    main()
