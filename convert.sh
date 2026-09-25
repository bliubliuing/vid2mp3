#!/usr/bin/env bash
# 把视频目录下的 mp4 批量提取转换为 MP3
# 用法: ./convert.sh [数量] [视频目录] [音频输出目录]
#   数量(可选): 本次最多转换几个新文件，缺省=全部
#   视频目录 / 音频输出目录(可选): 缺省使用下面的默认路径，可按需传入覆盖
# 已存在的 MP3 会自动跳过，不重复转换。

set -u

BASE="${VID2MP3_BASE:-$PWD}"
DEFAULT_SRC="$BASE/videos"
DEFAULT_DST="$BASE/mp3"

LIMIT="${1:-0}"
SRC="${2:-$DEFAULT_SRC}"
DST="${3:-$DEFAULT_DST}"

mkdir -p "$DST"

count=0
for f in "$SRC"/*.mp4; do
    name=$(basename "${f%.mp4}")
    out="$DST/$name.mp3"
    if [ -f "$out" ]; then
        echo "SKIP(已存在): $out"
        continue
    fi
    if ffmpeg -y -i "$f" -vn -acodec libmp3lame -q:a 2 "$out" -loglevel error; then
        echo "OK: $out"
        count=$((count + 1))
    else
        echo "FAIL: $f" >&2
        rm -f "$out"
    fi
    if [ "$LIMIT" -gt 0 ] && [ "$count" -ge "$LIMIT" ]; then
        echo "已达到本次转换上限 $LIMIT，停止。"
        break
    fi
done

total=$(ls "$DST"/*.mp3 2>/dev/null | wc -l)
echo "完成。本次新转换 $count 个，输出目录现有 MP3 共 $total 个。"
