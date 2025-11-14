/**
 * Base message interface
 */
export interface BaseMessage {
  type: string;
  timestamp: number;
}

/**
 * Speaker → Server Messages
 */

export interface SendAudioMessage {
  action: 'sendAudio';
  audioData: string; // Base64-encoded PCM
  timestamp: number;
  chunkId: string;
  duration?: number;
}

export interface PauseBroadcastMessage {
  action: 'pauseBroadcast';
  sessionId: string;
}

export interface ResumeBroadcastMessage {
  action: 'resumeBroadcast';
  sessionId: string;
}

export interface MuteBroadcastMessage {
  action: 'muteBroadcast';
  sessionId: string;
}

export interface UnmuteBroadcastMessage {
  action: 'unmuteBroadcast';
  sessionId: string;
}

export interface EndSessionMessage {
  action: 'endSession';
  sessionId: string;
  reason: string;
}

export interface GetSessionStatusMessage {
  action: 'getSessionStatus';
  sessionId: string;
}

export interface CreateSessionMessage {
  action: 'createSession';
  sourceLanguage: string;
  qualityTier: 'standard' | 'premium';
}

/**
 * Server → Speaker Messages
 */

export interface SessionCreatedMessage extends BaseMessage {
  type: 'sessionCreated';
  sessionId: string;
  sourceLanguage: string;
  qualityTier: string;
  connectionId: string;
  expiresAt: number;
}

export interface AudioQualityWarningMessage extends BaseMessage {
  type: 'audio_quality_warning';
  issue: 'snr_low' | 'clipping' | 'echo' | 'silence';
  message: string;
  details: Record<string, any>;
}

export interface SessionStatusMessage extends BaseMessage {
  type: 'sessionStatus';
  sessionId: string;
  isActive: boolean;
  listenerCount: number;
  languageDistribution: Record<string, number>;
  sessionDuration: number;
  createdAt: number;
  expiresAt: number;
}

/**
 * Listener → Server Messages
 */

export interface JoinSessionMessage {
  action: 'joinSession';
  sessionId: string;
  targetLanguage: string;
}

export interface SwitchLanguageMessage {
  action: 'switchLanguage';
  targetLanguage: string;
}

/**
 * Server → Listener Messages
 */

export interface SessionJoinedMessage extends BaseMessage {
  type: 'sessionJoined';
  sessionId: string;
  targetLanguage: string;
  sourceLanguage: string;
  connectionId: string;
  listenerCount: number;
  qualityTier: string;
}

export interface AudioMessage extends BaseMessage {
  type: 'audio';
  audioData: string; // Base64-encoded PCM
  format: 'pcm';
  sampleRate: number;
  channels: number;
  sequenceNumber: number;
}

export interface SpeakerPausedMessage extends BaseMessage {
  type: 'speakerPaused';
}

export interface SpeakerMutedMessage extends BaseMessage {
  type: 'speakerMuted';
}

export interface SpeakerResumedMessage extends BaseMessage {
  type: 'speakerResumed';
}

export interface SpeakerUnmutedMessage extends BaseMessage {
  type: 'speakerUnmuted';
}

/**
 * Common Messages (Both Speaker and Listener)
 */

export interface HeartbeatMessage {
  action: 'heartbeat';
  timestamp: number;
}

export interface HeartbeatAckMessage extends BaseMessage {
  type: 'heartbeatAck';
}

export interface ConnectionRefreshRequiredMessage extends BaseMessage {
  type: 'connectionRefreshRequired';
  refreshBy: number;
}

export interface RefreshConnectionMessage {
  action: 'refreshConnection';
  sessionId: string;
  targetLanguage?: string; // For listeners
}

export interface ConnectionRefreshCompleteMessage extends BaseMessage {
  type: 'connectionRefreshComplete';
  newConnectionId: string;
}

export interface SessionEndedMessage extends BaseMessage {
  type: 'sessionEnded';
  sessionId: string;
  reason: string;
}

export interface ErrorMessage extends BaseMessage {
  type: 'error';
  code: number;
  message: string;
  retryAfter?: number;
}

/**
 * Union types for type safety
 */

export type SpeakerToServerMessage =
  | SendAudioMessage
  | PauseBroadcastMessage
  | ResumeBroadcastMessage
  | MuteBroadcastMessage
  | UnmuteBroadcastMessage
  | EndSessionMessage
  | GetSessionStatusMessage
  | CreateSessionMessage
  | HeartbeatMessage
  | RefreshConnectionMessage;

export type ServerToSpeakerMessage =
  | SessionCreatedMessage
  | AudioQualityWarningMessage
  | SessionStatusMessage
  | HeartbeatAckMessage
  | ConnectionRefreshRequiredMessage
  | ConnectionRefreshCompleteMessage
  | SessionEndedMessage
  | ErrorMessage;

export type ListenerToServerMessage =
  | JoinSessionMessage
  | SwitchLanguageMessage
  | HeartbeatMessage
  | RefreshConnectionMessage;

export type ServerToListenerMessage =
  | SessionJoinedMessage
  | AudioMessage
  | SpeakerPausedMessage
  | SpeakerMutedMessage
  | SpeakerResumedMessage
  | SpeakerUnmutedMessage
  | HeartbeatAckMessage
  | ConnectionRefreshRequiredMessage
  | ConnectionRefreshCompleteMessage
  | SessionEndedMessage
  | ErrorMessage;

export type AnyMessage =
  | SpeakerToServerMessage
  | ServerToSpeakerMessage
  | ListenerToServerMessage
  | ServerToListenerMessage;
