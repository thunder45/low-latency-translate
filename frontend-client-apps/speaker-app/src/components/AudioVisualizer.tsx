import React, { useEffect, useRef, useState } from 'react';

interface AudioVisualizerProps {
  inputLevel: number; // 0-100
  isTransmitting: boolean;
}

/**
 * Audio visualizer component showing real-time input level
 * 
 * Requirements: 19.1, 19.2, 19.3, 19.4, 19.5
 */
export const AudioVisualizer: React.FC<AudioVisualizerProps> = ({
  inputLevel,
  isTransmitting,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number | null>(null);
  const levelHistoryRef = useRef<number[]>([]);
  const [averageLevel, setAverageLevel] = useState(0);
  const [showLowLevelWarning, setShowLowLevelWarning] = useState(false);
  const lowLevelTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Calculate 1-second rolling average
  useEffect(() => {
    // Add current level to history
    levelHistoryRef.current.push(inputLevel);

    // Keep only last 30 samples (assuming ~30 FPS, this is ~1 second)
    if (levelHistoryRef.current.length > 30) {
      levelHistoryRef.current.shift();
    }

    // Calculate average
    const sum = levelHistoryRef.current.reduce((acc, val) => acc + val, 0);
    const avg = sum / levelHistoryRef.current.length;
    setAverageLevel(Math.round(avg));

    // Check for low audio level (<5% for >3 seconds)
    if (inputLevel < 5 && isTransmitting) {
      if (!lowLevelTimerRef.current) {
        lowLevelTimerRef.current = setTimeout(() => {
          setShowLowLevelWarning(true);
        }, 3000);
      }
    } else {
      if (lowLevelTimerRef.current) {
        clearTimeout(lowLevelTimerRef.current);
        lowLevelTimerRef.current = null;
      }
      setShowLowLevelWarning(false);
    }
  }, [inputLevel, isTransmitting]);

  // Render visualization at 30+ FPS
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const render = () => {
      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Draw background
      ctx.fillStyle = '#f5f5f5';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Determine color based on level
      let barColor = '#4CAF50'; // Green (normal)
      if (inputLevel > 95) {
        barColor = '#f44336'; // Red (clipping)
      } else if (inputLevel > 80) {
        barColor = '#FFC107'; // Yellow (warning)
      }

      // Draw level bar
      const barWidth = (canvas.width * inputLevel) / 100;
      ctx.fillStyle = barColor;
      ctx.fillRect(0, 0, barWidth, canvas.height);

      // Draw level markers
      ctx.strokeStyle = '#ddd';
      ctx.lineWidth = 1;
      for (let i = 0; i <= 100; i += 20) {
        const x = (canvas.width * i) / 100;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }

      // Draw threshold lines
      // 80% threshold (yellow warning)
      const threshold80 = (canvas.width * 80) / 100;
      ctx.strokeStyle = '#FFC107';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(threshold80, 0);
      ctx.lineTo(threshold80, canvas.height);
      ctx.stroke();

      // 95% threshold (red clipping)
      const threshold95 = (canvas.width * 95) / 100;
      ctx.strokeStyle = '#f44336';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(threshold95, 0);
      ctx.lineTo(threshold95, canvas.height);
      ctx.stroke();

      // Continue animation
      animationFrameRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [inputLevel]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (lowLevelTimerRef.current) {
        clearTimeout(lowLevelTimerRef.current);
      }
    };
  }, []);

  const getWarningMessage = () => {
    if (inputLevel > 95) {
      return {
        type: 'clipping',
        message: 'Audio distortion detected. Reduce microphone volume',
        icon: '⚠️',
      };
    } else if (inputLevel > 80) {
      return {
        type: 'high',
        message: 'Audio level high. Consider reducing volume to avoid distortion',
        icon: '⚠️',
      };
    } else if (showLowLevelWarning) {
      return {
        type: 'low',
        message: 'Low audio level detected. Check if microphone is muted or too far',
        icon: '🔇',
      };
    }
    return null;
  };

  const warning = getWarningMessage();

  return (
    <div className="audio-visualizer-container">
      <div className="visualizer-header">
        <h3>Audio Input Level</h3>
        <div className="level-indicators">
          <span className="current-level">Current: {inputLevel}%</span>
          <span className="average-level">Avg: {averageLevel}%</span>
        </div>
      </div>

      <div className="canvas-container">
        <canvas
          ref={canvasRef}
          width={600}
          height={60}
          className="visualizer-canvas"
          aria-label={`Audio input level: ${inputLevel} percent`}
        />
        <div className="level-labels">
          <span>0%</span>
          <span>20%</span>
          <span>40%</span>
          <span>60%</span>
          <span className="threshold-label">80%</span>
          <span className="threshold-label">95%</span>
        </div>
      </div>

      {warning && (
        <div className={`warning-message warning-${warning.type}`} role="alert">
          <span className="warning-icon">{warning.icon}</span>
          <span className="warning-text">{warning.message}</span>
        </div>
      )}

      {!isTransmitting && (
        <div className="info-message">
          Audio transmission paused
        </div>
      )}

      <style>{`
        .audio-visualizer-container {
          display: flex;
          flex-direction: column;
          gap: 1rem;
          padding: 1.5rem;
          background-color: white;
          border-radius: 8px;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .visualizer-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .visualizer-header h3 {
          margin: 0;
          font-size: 1.125rem;
          font-weight: 600;
          color: #333;
        }

        .level-indicators {
          display: flex;
          gap: 1rem;
          font-size: 0.875rem;
        }

        .current-level {
          font-weight: 600;
          color: #4CAF50;
        }

        .average-level {
          color: #666;
        }

        .canvas-container {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .visualizer-canvas {
          width: 100%;
          height: 60px;
          border: 1px solid #ddd;
          border-radius: 4px;
        }

        .level-labels {
          display: flex;
          justify-content: space-between;
          font-size: 0.75rem;
          color: #666;
          padding: 0 0.25rem;
        }

        .threshold-label {
          font-weight: 600;
        }

        .warning-message {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.75rem 1rem;
          border-radius: 4px;
          font-weight: 500;
        }

        .warning-message.warning-clipping {
          background-color: #ffebee;
          color: #c62828;
          border-left: 4px solid #f44336;
        }

        .warning-message.warning-high {
          background-color: #fff3cd;
          color: #856404;
          border-left: 4px solid #FFC107;
        }

        .warning-message.warning-low {
          background-color: #e3f2fd;
          color: #1565c0;
          border-left: 4px solid #2196F3;
        }

        .warning-icon {
          font-size: 1.25rem;
        }

        .warning-text {
          flex: 1;
        }

        .info-message {
          padding: 0.75rem 1rem;
          background-color: #f5f5f5;
          color: #666;
          border-radius: 4px;
          text-align: center;
          font-style: italic;
        }

        @media (max-width: 768px) {
          .visualizer-header {
            flex-direction: column;
            align-items: flex-start;
            gap: 0.5rem;
          }

          .level-indicators {
            width: 100%;
            justify-content: space-between;
          }
        }
      `}</style>
    </div>
  );
};
