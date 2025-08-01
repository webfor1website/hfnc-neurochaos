import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import Plot from 'react-plotly.js';

function VisualizePage() {
  const location = useLocation();
  const [plots, setPlots] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    console.log('Location state:', JSON.stringify(location.state, null, 2));
    const { filename, shape, sampling_rate, channel_names, metrics } = location.state || {};

    if (!filename || !metrics || !channel_names || !shape) {
      console.log('Missing data:', { filename, metrics, channel_names, shape });
      setError('Missing or incomplete data from upload. Please try uploading again.');
      return;
    }

    const meanAmpPlot = {
      data: [{
        x: channel_names,
        y: metrics.map(m => m.mean_amplitude),
        type: 'bar',
        name: 'Mean Amplitude (µV)',
      }],
      layout: {
        title: 'Mean Amplitude',
        xaxis: { title: 'Channel', tickangle: 45 },
        yaxis: { title: 'µV' },
        height: 400,
        margin: { b: 150 },
      }
    };

    const muPsdPlot = {
      data: [{
        x: channel_names,
        y: metrics.map(m => m.mu_psd),
        type: 'bar',
        name: 'Mu PSD (µV²/Hz)',
      }],
      layout: {
        title: 'Mu Band PSD (8-13 Hz)',
        xaxis: { title: 'Channel', tickangle: 45 },
        yaxis: { title: 'µV²/Hz' },
        height: 400,
        margin: { b: 150 },
      }
    };

    const erdPlot = {
      data: [{
        x: channel_names,
        y: metrics.map(m => m.erd_amplitude),
        type: 'bar',
        name: 'ERD Amplitude (µV²)',
      }],
      layout: {
        title: 'ERD Amplitude',
        xaxis: { title: 'Channel', tickangle: 45 },
        yaxis: { title: 'µV²' },
        height: 400,
        margin: { b: 150 },
      }
    };

    const latencyPlot = {
      data: [{
        x: channel_names,
        y: metrics.map(m => m.event_latency),
        type: 'bar',
        name: 'Event Latency (s)',
      }],
      layout: {
        title: 'Event Onset Latency',
        xaxis: { title: 'Channel', tickangle: 45 },
        yaxis: { title: 'Seconds' },
        height: 400,
        margin: { b: 150 },
      }
    };

    setPlots([meanAmpPlot, muPsdPlot, erdPlot, latencyPlot]);
    setError(null);
  }, [location.state]);

  return (
    <div>
      <h1>EEG Data Visualization: {location.state?.filename || 'Unknown'}</h1>
      {error ? (
        <p style={{ color: 'red' }}>{error}</p>
      ) : plots.length > 0 ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          {plots.map((plot, idx) => (
            <Plot
              key={idx}
              data={plot.data}
              layout={plot.layout}
            />
          ))}
        </div>
      ) : (
        <p>Loading data...</p>
      )}
    </div>
  );
}

export default VisualizePage; 
