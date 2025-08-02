from flask import Flask, request
from flask_cors import CORS
import os
import numpy as np
from mne.io import read_raw_edf
from mne.time_frequency import psd_array_multitaper, tfr_array_morlet
import json
import logging
from chaos_grid import ChaosGrid
import mne
import boto3
from botocore.exceptions import ClientError

app = Flask(__name__)
CORS(app, resources={r"/upload": {"origins": ["http://localhost:3000", "https://hfnc-neurochaos-fvgs-brlm2q88g-jake-thompsons-projects-e8c91d40.vercel.app"]}})

logging.basicConfig(filename='app.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)
BUCKET_NAME = 'hfnc-neurochaos-eeg'

chaos_grid = ChaosGrid()

@app.route('/')
def home():
    """Health check route."""
    logger.debug("Root route accessed")
    return "Backend is running!"

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
        try:
            s3_client.upload_fileobj(
                file,
                BUCKET_NAME,
                file.filename,
                ExtraArgs={'ACL': 'public-read'}
            )
            file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{file.filename}"
            logger.debug(f"Uploaded to S3: {file_url}")

            local_file = f"/tmp/{file.filename}"
            s3_client.download_file(BUCKET_NAME, file.filename, local_file)

            logger.debug(f"Loading EDF: {local_file}")
            raw = read_raw_edf(local_file, preload=True, verbose='error')
            data = raw.get_data()
            sfreq = raw.info['sfreq']
            channel_names = raw.ch_names
            annotations = raw.annotations
            logger.debug(f"EDF loaded: shape={data.shape}, sfreq={sfreq}, channels={len(channel_names)}")

            freqs = np.arange(8, 14, 0.5)
            n_cycles = freqs / 2.0
            power = tfr_array_morlet(data[None, :, :], sfreq=sfreq, freqs=freqs, n_cycles=n_cycles, output='power')
            power = power.squeeze(0).mean(axis=1)

            baseline_end = int(5 * sfreq)
            baseline_power = power[:, :baseline_end].mean(axis=1, keepdims=True)
            power_change = (power - baseline_power) / baseline_power

            erd_threshold = -0.3
            ers_threshold = 0.3
            new_annotations = []
            for ch in range(data.shape[0]):
                erd_times = np.where(power_change[ch] < erd_threshold)[0] / sfreq
                ers_times = np.where(power_change[ch] > ers_threshold)[0] / sfreq
                for t in erd_times:
                    new_annotations.append({'onset': float(t), 'duration': 0.5, 'description': f'ERD_ch{ch}'})
                for t in ers_times:
                    new_annotations.append({'onset': float(t), 'duration': 0.5, 'description': f'ERS_ch{ch}'})

            if new_annotations:
                raw.set_annotations(raw.annotations + mne.Annotations(
                    onset=[a['onset'] for a in new_annotations],
                    duration=[a['duration'] for a in new_annotations],
                    description=[a['description'] for a in new_annotations]
                ))

            metrics = []
            for ch in range(data.shape[0]):
                mean_amp = float(np.mean(data[ch]) * 1e6)
                psd, freqs = psd_array_multitaper(data[ch], sfreq, fmin=8, fmax=13, adaptive=True, normalization='full', verbose=False)
                mu_psd = float(np.mean(psd) * 1e12)
                channel_erd_times = [a['onset'] for a in new_annotations if a['description'].startswith(f'ERD_ch{ch}')]
                erd_amp = 0.0
                if channel_erd_times:
                    t_start = int(channel_erd_times[0] * sfreq)
                    t_end = min(t_start + int(1.5 * sfreq), data.shape[1])
                    baseline_psd, _ = psd_array_multitaper(data[ch, :baseline_end], sfreq, fmin=8, fmax=13, verbose=False)
                    event_psd, _ = psd_array_multitaper(data[ch, t_start:t_end], sfreq, fmin=8, fmax=13, verbose=False)
                    erd_amp = float((np.mean(baseline_psd) - np.mean(event_psd)) * 1e12)
                latency = float(channel_erd_times[0] if channel_erd_times else 0.0)
                metrics.append({
                    'mean_amplitude': mean_amp,
                    'mu_psd': mu_psd,
                    'erd_amplitude': erd_amp,
                    'event_latency': latency,
                    'erd_count': len([a for a in new_annotations if a['description'].startswith(f'ERD_ch{ch}')]),
                    'ers_count': len([a for a in new_annotations if a['description'].startswith(f'ERS_ch{ch}')])
                })

            chaos_metrics = chaos_grid.process(data)
            logger.debug(f"Chaos metrics: {chaos_metrics}")

            os.remove(local_file)

            response = {
                'message': 'File uploaded successfully',
                'filename': file.filename,
                'file_url': file_url,
                'shape': [int(data.shape[0]), int(data.shape[1])],
                'sampling_rate': float(sfreq),
                'channel_names': channel_names,
                'metrics': metrics,
                'chaos_metrics': chaos_metrics,
                'annotations': [{'onset': a['onset'], 'duration': a['duration'], 'description': a['description']} for a in raw.annotations]
            }
            logger.debug(f"Sending response: {json.dumps(response, indent=2)}")
            return response, 200
        except Exception as e:
            logger.error(f"Error processing EDF: {str(e)}")
            return {'error': f'Invalid EDF file: {str(e)}'}, 400
    logger.error("Only .edf files are allowed")
    return {'error': 'Only .edf files are allowed'}, 400
