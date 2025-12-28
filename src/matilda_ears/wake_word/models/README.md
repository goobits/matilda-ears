# Wake Word Models

Place custom OpenWakeWord models (.onnx files) in this directory.

## Naming Convention

Models should be named: `hey_<agent>.onnx`

Examples:
- `hey_matilda.onnx` - Custom model for "Hey Matilda"
- `hey_bob.onnx` - Custom model for "Hey Bob"
- `hey_maria.onnx` - Custom model for "Hey Maria"

## Pre-trained Models

If no custom model exists, OpenWakeWord will try to load pre-trained models:
- `alexa` - Amazon Alexa wake word
- `hey_mycroft` - Mycroft AI assistant
- `hey_jarvis` - Jarvis assistant
- `hey_rhasspy` - Rhasspy voice assistant

Note: Pre-trained models only work for their specific phrases.

## Training Custom Models

1. **Generate synthetic training data**:
   ```bash
   pip install synthetic-speech-dataset-generation
   python -c "
   from synthetic_speech_dataset_generation import generate_positive_samples
   generate_positive_samples('Hey Matilda', n_samples=5000, output_dir='positive/')
   "
   ```

2. **Collect negative samples** (background noise, other speech):
   ```bash
   # Use any audio dataset without the wake word
   ```

3. **Train using Google Colab notebook**:
   https://github.com/dscripka/openWakeWord/blob/main/notebooks/training_models.ipynb

4. **Export model** and place the `.onnx` file here.

## Model Requirements

- Format: ONNX
- Input: 80ms audio frames (1280 samples @ 16kHz)
- Output: Confidence score (0.0-1.0)

## Performance

OpenWakeWord models are optimized for:
- Low CPU usage (~1-2% on modern CPUs)
- Low latency (~80ms detection delay)
- Low memory footprint (~10-50MB per model)
