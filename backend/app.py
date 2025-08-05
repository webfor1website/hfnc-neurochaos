from flask import Flask, request
from flask_cors import CORS
import os
import numpy as np
from mne.io import read_raw_edf
from mne.time_frequency import psd_array_multitaper
import json
import logging
from chaos_grid import ChaosGrid
from io import BytesIO

app = Flask(__name__)
CORS(app, resources={r"/upload": {"origins": ["http://localhost:3000", "https://hfnc-neurochaos-vfgs.vercel.app"]}})

# Configure logging
logging.basicConfig(filename='app.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use temporary directory for uploads
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/tmp/uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize ChaosGrid
chaos_grid = ChaosGrid()

@app.route('/upload', methods=['POST'])
def upload_file():
    logger.debug("Received upload request")
    if 'file' not in request.files:
        logger.error("No file part in request")
        return {'error': 'No file part'}, 400
    file = request.files['file']
    if file.filename == '':
        logger.error("No selected file")
        return {'error': 'No selected file'}, 400
    if file and file.filename.endswith('.edf'):
        # Process file in memory
        try:
            file_content = file.read()
            file_stream = BytesIO(file_content)
            logger.debug(f"Loading EDF from memory: {file.filename}")
            raw = read_raw_edf(file_stream, preload=True, verbose='error')
            data = raw.get_data()
            sfreq = raw.info['sfreq']
            channel_names = raw.ch_names
            annotations = raw.annotations
            logger.debug(f"EDF loaded: shape={data.shape}, sfreq={sfreq}, channels={len(channel_names)}")

            # Compute EEG metrics
            metrics = []
            for ch in range(data.shape[0]):
                mean_amp = float(np.mean(data[ch]) * 1e6)
                psd, freqs = psd_array_multitaper(data[ch], sfreq, fmin=8, fmax=13, adaptive=True, normalization='full', verbose=False)
                mu_psd = float(np.mean(psd) * 1e12)
                event_times = [a['onset'] for a in annotations if a['description'] in ['T1', 'T2']]
                erd_amp = 0.0
                if event_times:
                    t_start = int(event_times[0] * sfreq)
                    t_end = min(t_start + int(1.5 * sfreq), data.shape[1])
                    baseline_psd, _ = psd_array_multitaper(data[ch, :t_start], sfreq, fmin=8, fmax=13, verbose=False)
                    event_psd, _ = psd_array_multitaper(data[ch, t_start:t_end], sfreq, fmin=8, fmax=13, verbose=False)
                    erd_amp = float((np.mean(baseline_psd) - np.mean(event_psd)) * 1e12)
                latency = float(event_times[0] if event_times else 0.0)
                metrics.append({
                    'mean_amplitude': mean_amp,
                    'mu_psd': mu_psd,
                    'erd_amplitude': erd_amp,
                    'event_latency': latency
                })

            # Chaos grid processing
            chaos_metrics = chaos_grid.process(data)
            logger.debug(f"Chaos metrics: {chaos_metrics}")

            response = {
                'message': 'File uploaded successfully',
                'filename': file.filename,
                'shape': [int(data.shape[0]), int(data.shape[1])],
                'sampling_rate': float(sfreq),
                'channel_names': channel_names,
                'metrics': metrics
            }
            logger.debug(f"Sending response: {json.dumps(response, indent=2)}")
            return response, 200
        except Exception as e:
            logger.error(f"Error processing EDF: {str(e)}")
            return {'error': f'Invalid EDF file: {str(e)}'}, 400
    logger.error("Only .edf files are allowed")
    return {'error': 'Only .edf files are allowed'}, 400

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
