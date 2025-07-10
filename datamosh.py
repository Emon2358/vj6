import subprocess
import os
import random
import sys
import requests
from bs4 import BeautifulSoup
import time

def get_video_duration(video_path):
    """
    FFmpegを使って動画の長さを秒単位で取得します。
    """
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", video_path
        ]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return float(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f"ffprobeエラー: {e.stderr}")
        return None
    except ValueError:
        print(f"ffprobe出力の解析エラー: {result.stdout}")
        return None

def datamosh_video(input_video_path, output_video_path, glitches_to_apply=5, glitch_strength=5000):
    """
    PythonとFFmpegを使って動画にデータモッシングを施します。

    Args:
        input_video_path (str): 入力動画ファイルのパス。
        output_video_path (str): 出力動画ファイルのパス。
        glitches_to_apply (int): 適用するグリッチの回数。
        glitch_strength (int): グリッチの強さ（バイト数）。数値が大きいほど破損が大きくなります。
    """

    if not os.path.exists(input_video_path):
        print(f"エラー: 入力ファイルが見つかりません - {input_video_path}")
        sys.exit(1) # スクリプトを終了

    # 一時ファイルのパスを設定
    temp_inter_video = "temp_inter.avi"
    temp_glitched_video = "temp_glitched.avi"

    print("ステップ1: Iフレーム間隔を広く設定し、AVIに変換中...")
    try:
        subprocess.run([
            "ffmpeg", "-i", input_video_path,
            "-vf", "setpts=PTS/1.0",
            "-q:v", "0",
            "-g", "99999", # Iフレーム間隔を非常に大きく設定
            "-f", "avi", temp_inter_video
        ], check=True, capture_output=True, text=True)
        print("一時AVIファイル作成完了。")
    except subprocess.CalledProcessError as e:
        print(f"FFmpegエラー (ステップ1): {e.stderr}")
        if os.path.exists(temp_inter_video):
            os.remove(temp_inter_video)
        sys.exit(1)

    print(f"ステップ2: バイナリ破損を {glitches_to_apply} 回適用中...")
    try:
        with open(temp_inter_video, "rb") as f:
            video_data = bytearray(f.read())

        video_size = len(video_data)
        print(f"ビデオデータサイズ: {video_size} バイト")

        # 少なくともビデオデータの5%はスキップする（ヘッダー等の破損を避けるため）
        min_offset = int(video_size * 0.05)
        if min_offset > video_size - glitch_strength - 1:
            min_offset = 0 # データが小さい場合はスキップしない

        for _ in range(glitches_to_apply):
            start_offset = random.randint(min_offset, video_size - glitch_strength - 1)
            if start_offset < 0:
                start_offset = 0
            end_offset = start_offset + glitch_strength

            for i in range(start_offset, min(end_offset, video_size)):
                video_data[i] = random.randint(0, 255)

            print(f"  破損適用: オフセット {start_offset} から {end_offset} ({glitch_strength} バイト)")

        with open(temp_glitched_video, "wb") as f:
            f.write(video_data)
        print("バイナリ破損適用完了。")

    except Exception as e:
        print(f"ファイル処理エラー (ステップ2): {e}")
        if os.path.exists(temp_inter_video):
            os.remove(temp_inter_video)
        if os.path.exists(temp_glitched_video):
            os.remove(temp_glitched_video)
        sys.exit(1)

    print("ステップ3: 破損したAVIファイルを最終出力形式に変換中...")
    try:
        subprocess.run([
            "ffmpeg", "-i", temp_glitched_video,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-y",
            output_video_path
        ], check=True, capture_output=True, text=True)
        print(f"データモッシュ完了: {output_video_path}")
    except subprocess.CalledProcessError as e:
        print(f"FFmpegエラー (ステップ3): {e.stderr}")
        sys.exit(1)
    finally:
        if os.path.exists(temp_inter_video):
            os.remove(temp_inter_video)
        if os.path.exists(temp_glitched_video):
            os.remove(temp_glitched_video)
        print("一時ファイルを削除しました。")

def download_and_process_random_video(archive_url, glitches_to_apply, glitch_strength):
    """
    指定されたアーカイブURLからMP4ファイルをダウンロードし、ランダムに1分間切り取り、
    そのセグメントにデータモッシュを適用します。
    """
    temp_dir = "temp_archive_videos"
    os.makedirs(temp_dir, exist_ok=True)
    downloaded_files = []

    print(f"アーカイブURLからMP4ファイルを検索中: {archive_url}")
    try:
        response = requests.get(archive_url)
        response.raise_for_status() # HTTPエラーがあれば例外を発生させる
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.endswith('.mp4'):
                video_url = f"{archive_url}/{href}" if not href.startswith('http') else href
                file_name = os.path.join(temp_dir, os.path.basename(video_url))
                print(f"ダウンロード中: {video_url} -> {file_name}")
                
                with requests.get(video_url, stream=True) as r:
                    r.raise_for_status()
                    with open(file_name, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                downloaded_files.append(file_name)
                print(f"ダウンロード完了: {file_name}")

    except requests.exceptions.RequestException as e:
        print(f"URLからのダウンロードエラー: {e}")
        # クリーンアップ
        for f in downloaded_files:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
        return None
    except Exception as e:
        print(f"HTML解析またはファイル処理エラー: {e}")
        # クリーンアップ
        for f in downloaded_files:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
        return None

    if not downloaded_files:
        print("エラー: ダウンロードされたMP4ファイルが見つかりませんでした。")
        # クリーンアップ
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
        return None

    # ランダムに1つ選択
    selected_video_path = random.choice(downloaded_files)
    print(f"ランダムに選択された動画: {selected_video_path}")

    # 動画の長さを取得
    duration = get_video_duration(selected_video_path)
    if duration is None:
        print(f"エラー: {selected_video_path} の長さを取得できませんでした。")
        # クリーンアップ
        for f in downloaded_files:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
        return None

    # 1分（60秒）のセグメントを切り出す
    segment_duration = 60 # seconds
    if duration < segment_duration:
        print(f"警告: 動画の長さが1分未満です（{duration:.2f}秒）。全動画を使用します。")
        start_time = 0
        cut_output_path = os.path.join(temp_dir, f"cut_{os.path.basename(selected_video_path)}")
        try:
            # -c copy はIフレームの問題でデータモッシュと相性が悪い可能性があるため、再エンコードする
            subprocess.run([
                "ffmpeg", "-i", selected_video_path,
                "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-y", cut_output_path
            ], check=True, capture_output=True, text=True)
            print(f"動画全体を再エンコードしてコピーしました: {cut_output_path}")
        except subprocess.CalledProcessError as e:
            print(f"FFmpegエラー (動画コピー/再エンコード): {e.stderr}")
            cut_output_path = None # エラーの場合はNoneを設定
    else:
        max_start_time = duration - segment_duration
        start_time = random.uniform(0, max_start_time)
        start_time_str = f"{int(start_time // 3600):02}:{int((start_time % 3600) // 60):02}:{int(start_time % 60):02}"
        print(f"動画を {start_time_str} から1分間切り取り中...")

        cut_output_path = os.path.join(temp_dir, f"cut_{os.path.basename(selected_video_path)}")
        try:
            subprocess.run([
                "ffmpeg", "-ss", str(start_time), "-i", selected_video_path,
                "-t", str(segment_duration), "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-y", cut_output_path
            ], check=True, capture_output=True, text=True)
            print(f"動画切り取り完了: {cut_output_path}")
        except subprocess.CalledProcessError as e:
            print(f"FFmpegエラー (動画切り取り): {e.stderr}")
            cut_output_path = None

    if cut_output_path is None or not os.path.exists(cut_output_path):
        print("エラー: 動画の切り取りに失敗しました。")
        # クリーンアップ
        for f in downloaded_files:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
        return None

    # 切り取った動画にデータモッシュを適用
    # 出力ファイル名はユニークにするためにタイムスタンプを追加
    timestamp = int(time.time())
    final_output_name = f"datamoshed_archive_video_{timestamp}.mp4"
    final_output_path = os.path.join(os.getcwd(), final_output_name) # カレントディレクトリに保存
    print(f"切り取った動画にデータモッシュを適用中: {cut_output_path} -> {final_output_path}")
    datamosh_video(cut_output_path, final_output_path, glitches_to_apply, glitch_strength)

    # 一時ファイルをクリーンアップ
    for f in downloaded_files:
        if os.path.exists(f):
            os.remove(f)
    if os.path.exists(cut_output_path):
        os.remove(cut_output_path)
    if os.path.exists(temp_dir):
        os.rmdir(temp_dir)
    print("一時ファイルを削除しました。")

    return final_output_path


if __name__ == "__main__":
    # コマンドライン引数から入力ファイル名と出力ファイル名を取得
    if len(sys.argv) < 3:
        print("使用法:")
        print("  ローカルファイルの場合: python datamosh.py <入力ファイル名> <出力ファイル名> [グリッチ回数] [グリッチ強度]")
        print("  アーカイブURLの場合: python datamosh.py --archive <アーカイブURL> <グリッチ回数> <グリッチ強度>")
        sys.exit(1)

    if sys.argv[1] == "--archive":
        if len(sys.argv) < 5:
            print("使用法: python datamosh.py --archive <アーカイブURL> <グリッチ回数> <グリッチ強度>")
            sys.exit(1)
        archive_url = sys.argv[2]
        glitches = int(sys.argv[3])
        strength = int(sys.argv[4])
        
        output_file = download_and_process_random_video(archive_url, glitches, strength)
        if output_file:
            # GitHub Actionsでこのパスをキャプチャするために標準出力に出力
            print(output_file) 
        else:
            print("データモッシュ処理が失敗しました。", file=sys.stderr)
            sys.exit(1)

    else:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        glitches = int(sys.argv[3]) if len(sys.argv) > 3 else 10 # デフォルトは10回
        strength = int(sys.argv[4]) if len(sys.argv) > 4 else 8000 # デフォルトは8000バイト

        datamosh_video(input_file, output_file, glitches_to_apply=glitches, glitch_strength=strength)
