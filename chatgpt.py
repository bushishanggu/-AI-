import os
import requests
from openai import OpenAI
from moviepy.editor import *
import pyttsx3
import time

# 初始化OpenAI客户端
client = OpenAI(
    base_url='https://cloud.perfxlab.cn/v1',
    api_key='sk-A0DJMZLV5ecTx8oI3313008724274eC08aB01659Da06E4D6'
)

# 1. 根据关键词生成故事
def generate_story(keyword):
    story = client.chat.completions.create(
        model="Llama3-Chinese_v2",
        messages=[
            {"role": "system", "content": "You are a storyteller."},
            {"role": "user", "content": f"Write a story about {keyword}."}
        ],
        temperature=1,
        max_tokens=300,
        n=1
    )
    return story.choices[0].message.content


# 2. 使用详细的提示词生成图片，增加一致的风格描述
def generate_image(prompt, image_index, negative_prompt="No human face, no people, no portraits, no distorted faces, no weird expressions, no text, no watermarks"):
    url = "https://cloud.perfxlab.cn/sdapi/v1/txt2img"

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer sk-pLeeRdK8XFuG6XZ13f13D1Bd60Db455d8a7fDdC5Be6753Db'
    }

    # 增加统一的风格描述，例如“cinematic lighting”和“consistent art style”
    detailed_prompt = f"{prompt}, high quality, photorealistic, cinematic lighting, consistent art style, natural lighting, sharp focus, no people"

    payload = {
        "model": "StableDiffusion",
        "prompt": detailed_prompt,
        "negative_prompt": negative_prompt,
        "steps": 50,  # 减少steps以避免超时
        "width": 512,
        "height": 512,
        "n_iter": 1
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)  # 增加超时等待时间
        response.raise_for_status()
    except requests.exceptions.Timeout:
        print(f"Request timed out for prompt: {prompt}")
        return
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return

    if response.status_code == 200:
        data = response.json()
        images = data.get('images', [])
        if not images:
            print(f"No images returned for prompt: {prompt}")
            return

        for idx, image_url in enumerate(images):
            print(f"Image {image_index}_{idx} URL: {image_url}")
            try:
                img_response = requests.get(image_url)
                img_response.raise_for_status()

                image_path = f'image_{image_index}_{idx}.png'
                with open(image_path, 'wb') as f:
                    f.write(img_response.content)
                print(f"Downloaded image_{image_index}_{idx}.png from {image_url}")

            except Exception as e:
                print(f"Failed to download image from {image_url}: {e}")
    else:
        print(f"Failed to generate image. Status code: {response.status_code}, response: {response.text}")


# 3. 添加重试机制的图片生成函数
def generate_image_with_retry(prompt, image_index, retry_limit=3):
    for attempt in range(retry_limit):
        try:
            generate_image(prompt, image_index)
            break
        except Exception as e:
            print(f"Attempt {attempt + 1} failed with error: {e}")
            if attempt < retry_limit - 1:
                print("Retrying...")
                time.sleep(2)  # 等待2秒后重试
            else:
                print("All retries failed.")


# 4. 使用 pyttsx3 将故事文本转换为音频
def text_to_speech(text, output_file):
    engine = pyttsx3.init()
    engine.save_to_file(text, output_file)  # 保存为音频文件
    engine.runAndWait()
    print(f"Audio saved to {output_file}")


# 5. 创建图片剪辑并合成视频
def create_image_clips(image_count, clip_duration=3):
    image_clips = []
    for i in range(image_count):
        try:
            img_path = f'image_{i}_0.png'
            print(f"Loading image: {img_path}")
            img_clip = ImageClip(img_path, duration=clip_duration)  # 每张图片展示clip_duration秒
            image_clips.append(img_clip)
        except Exception as e:
            print(f"Error loading {img_path}: {e}")
    return image_clips


# 6. 合成图片和音频为视频
def create_video_from_images_and_audio(image_count, audio_file, output_file, clip_duration=3):
    image_clips = create_image_clips(image_count, clip_duration)
    if len(image_clips) == 0:
        print("No valid images to create the video.")
        return

    try:
        video = concatenate_videoclips(image_clips, method="compose")
        audio_clip = AudioFileClip(audio_file)

        # 调整音频长度与视频的剪辑时长相匹配
        if video.duration > audio_clip.duration:
            video = video.subclip(0, audio_clip.duration)
        else:
            audio_clip = audio_clip.subclip(0, video.duration)

        video = video.set_audio(audio_clip)
        video.write_videofile(output_file, fps=24)
        print(f"Video saved to {output_file}")
    except Exception as e:
        print(f"Failed to create video: {e}")


# 7. 动态生成故事部分（基于生成的故事内容）
def generate_story_parts(story):
    # 解析故事内容，并提取不同场景或关键事件的描述
    story_lines = story.split(".")
    story_parts = []

    for line in story_lines:
        if len(line.strip()) > 0:
            story_parts.append(line.strip())

    return story_parts


# 主流程
def main():
    # 首先向用户询问视频的主题
    print("您好，请问您想要生成的视频的主题是什么？")
    keyword = input("请输入视频主题: ")

    # 1. 生成故事
    story = generate_story(keyword)
    print("生成的故事内容: \n", story)

    # 2. 根据生成的故事动态解析更多的场景描述
    story_parts = generate_story_parts(story)

    # 3. 根据每个故事部分生成对应图片，并确保风格一致
    for idx, part in enumerate(story_parts):
        generate_image_with_retry(part, idx)
        generate_image_with_retry(f"Different view of {part}", idx + len(story_parts))

    # 4. 将故事生成音频（使用本地pyttsx3 TTS引擎）
    text_to_speech(story, "story_audio.mp3")

    # 5. 合成图片和音频生成视频
    create_video_from_images_and_audio(len(story_parts) * 2, "story_audio.mp3", "final_story_video.mp4", clip_duration=3)


# 示例调用
main()
