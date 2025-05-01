import sounddevice as sd

def check_sample_rate_support(device_id, samplerate, channels=1, dtype='float32'):
    """檢查指定設備是否支持某個取樣率"""
    try:
        sd.check_input_settings(device=device_id, channels=channels, dtype=dtype, samplerate=samplerate)
        return True
    except sd.PortAudioError:
        return False

def list_supported_sample_rates(sample_rates=[8000, 16000, 22050, 44100, 48000, 96000]):
    """列出所有輸入設備支持的取樣率"""
    devices = sd.query_devices()
    print("正在檢查所有輸入設備的支持取樣率：\n")
    
    for device in devices:
        if device['max_input_channels'] > 0:  # 只檢查輸入設備
            device_id = device['index']
            device_name = device['name']
            print(f"設備 ID: {device_id}, 名稱: {device_name}")
            supported_rates = []
            for rate in sample_rates:
                if check_sample_rate_support(device_id, rate):
                    supported_rates.append(rate)
            if supported_rates:
                print(f"  支持的取樣率: {', '.join(map(str, supported_rates))} Hz")
            else:
                print("  無支持的取樣率（在測試的範圍內）")
            print()

if __name__ == "__main__":
    list_supported_sample_rates()