/**
 * Kinesis Video Streams WebRTC Service
 * 
 * Manages WebRTC connections using AWS Kinesis Video Streams
 * Handles signaling, peer connections, and media streaming
 */
import {
  SignalingClient,
  Role,
} from 'amazon-kinesis-video-streams-webrtc';

/**
 * AWS credentials for KVS access
 */
export interface AWSCredentials {
  accessKeyId: string;
  secretAccessKey: string;
  sessionToken?: string;
}

/**
 * Configuration for KVS WebRTC
 */
export interface KVSWebRTCConfig {
  channelARN: string;
  channelEndpoint: string;
  region: string;
  credentials: AWSCredentials;
  role: 'MASTER' | 'VIEWER';
  clientId?: string;
}

/**
 * ICE server configuration from KVS
 */
interface ICEServer {
  urls: string | string[];
  username?: string;
  credential?: string;
}

/**
 * KVS WebRTC Service for low-latency audio streaming
 * 
 * Features:
 * - UDP-based media transport (<500ms latency)
 * - Managed STUN/TURN servers
 * - Automatic NAT traversal
 * - Native binary audio (no Base64 overhead)
 */
export class KVSWebRTCService {
  private signalingClient: SignalingClient | null = null;
  private peerConnection: RTCPeerConnection | null = null;
  private localStream: MediaStream | null = null;
  private config: KVSWebRTCConfig;
  private remoteClientId: string | null = null;
  
  // Event handlers
  public onTrackReceived?: (stream: MediaStream) => void;
  public onConnectionStateChange?: (state: RTCPeerConnectionState) => void;
  public onICEConnectionStateChange?: (state: RTCIceConnectionState) => void;
  public onError?: (error: Error) => void;

  constructor(config: KVSWebRTCConfig) {
    this.config = config;
  }

  /**
   * Connect to KVS as Master (Speaker)
   * Master can broadcast audio to multiple viewers
   */
  async connectAsMaster(): Promise<void> {
    try {
      console.log('[KVS] Connecting as Master (Speaker)...');
      
      // 1. Create signaling client
      this.signalingClient = new SignalingClient({
        channelARN: this.config.channelARN,
        channelEndpoint: this.config.channelEndpoint,
        role: Role.MASTER,
        region: this.config.region,
        credentials: this.config.credentials,
        systemClockOffset: 0,
      });
      
      // 2. Get ICE servers (STUN/TURN)
      const iceServers = await this.getICEServers();
      console.log('[KVS] ICE servers obtained:', iceServers.length);
      
      // 3. Create peer connection
      this.peerConnection = new RTCPeerConnection({
        iceServers: iceServers,
        iceTransportPolicy: 'all', // Use TURN if direct connection fails
      });
      
      // 4. Set up connection event handlers
      this.setupConnectionHandlers();
      
      // 5. Get microphone stream
      console.log('[KVS] Requesting microphone access...');
      this.localStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      
      console.log('[KVS] Microphone access granted');
      
      // 6. Add audio track to peer connection
      this.localStream.getTracks().forEach(track => {
        this.peerConnection!.addTrack(track, this.localStream!);
        console.log('[KVS] Added audio track to peer connection');
      });
      
      // 7. Set up signaling handlers
      this.setupSignalingHandlers();
      
      // 8. Open signaling connection
      console.log('[KVS] Opening signaling channel...');
      await this.signalingClient.open();
      
      console.log('[KVS] Connected as Master, ready for viewers');
    } catch (error) {
      const err = error instanceof Error ? error : new Error('Failed to connect as Master');
      console.error('[KVS] Master connection failed:', err);
      this.onError?.(err);
      throw err;
    }
  }

  /**
   * Connect to KVS as Viewer (Listener)
   * Viewer receives audio from the master
   * 
   * @param retries Number of retry attempts if connection fails
   * @param initialDelayMs Initial delay between retries in milliseconds
   */
  async connectAsViewer(retries: number = 3, initialDelayMs: number = 2000): Promise<void> {
    let lastError: Error | null = null;
    let delayMs = initialDelayMs;
    
    for (let attempt = 1; attempt <= retries; attempt++) {
      try {
        console.log(`[KVS] Viewer connection attempt ${attempt}/${retries}...`);
        
        // Attempt connection
        await this.doConnectAsViewer();
        
        console.log('[KVS] Viewer connection successful!');
        return; // Success!
        
      } catch (error) {
        lastError = error instanceof Error ? error : new Error('Failed to connect as Viewer');
        console.warn(`[KVS] Attempt ${attempt} failed:`, lastError.message);
        
        // Cleanup failed connection attempt
        this.cleanupPartialConnection();
        
        // If this was the last attempt, throw the error
        if (attempt === retries) {
          console.error('[KVS] All connection attempts exhausted');
          this.onError?.(lastError);
          throw lastError;
        }
        
        // Wait before retrying (exponential backoff)
        console.log(`[KVS] Waiting ${delayMs}ms before retry...`);
        await new Promise(resolve => setTimeout(resolve, delayMs));
        delayMs = Math.min(delayMs * 1.5, 10000); // Cap at 10 seconds
      }
    }
    
    // Should never reach here, but just in case
    throw lastError || new Error('Failed to connect as Viewer');
  }

  /**
   * Internal method to perform actual viewer connection
   */
  private async doConnectAsViewer(): Promise<void> {
    console.log('[KVS] Connecting as Viewer (Listener)...');
    
    // 1. Create signaling client
    this.signalingClient = new SignalingClient({
      channelARN: this.config.channelARN,
      channelEndpoint: this.config.channelEndpoint,
      role: Role.VIEWER,
      region: this.config.region,
      credentials: this.config.credentials,
      clientId: this.config.clientId || this.generateClientId(),
      systemClockOffset: 0,
    });
    
    // 2. Get ICE servers
    const iceServers = await this.getICEServers();
    console.log('[KVS] ICE servers obtained:', iceServers.length);
    
    // 3. Create peer connection
    this.peerConnection = new RTCPeerConnection({
      iceServers: iceServers,
      iceTransportPolicy: 'all',
    });
    
    // 4. Set up connection event handlers
    this.setupConnectionHandlers();
    
    // 5. Handle incoming audio track from master
    this.peerConnection.ontrack = (event) => {
      console.log('[KVS] Received media track from Master');
      if (event.streams && event.streams[0]) {
        this.onTrackReceived?.(event.streams[0]);
      }
    };
    
    // 6. Set up signaling handlers
    this.setupSignalingHandlers();
    
    // 7. Open signaling connection with timeout
    console.log('[KVS] Opening signaling channel...');
    
    // Create promise that rejects on timeout
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => reject(new Error('Signaling channel connection timeout')), 15000);
    });
    
    // Race between actual open and timeout
    await Promise.race([
      this.signalingClient.open(),
      timeoutPromise
    ]);
    
    console.log('[KVS] Connected as Viewer, waiting for media from Master');
  }

  /**
   * Cleanup partial connection on failure
   */
  private cleanupPartialConnection(): void {
    try {
      if (this.peerConnection) {
        this.peerConnection.close();
        this.peerConnection = null;
      }
      
      if (this.signalingClient) {
        this.signalingClient.close();
        this.signalingClient = null;
      }
    } catch (error) {
      console.warn('[KVS] Error during cleanup:', error);
    }
  }

  /**
   * Get ICE servers (STUN/TURN) from KVS
   */
  private async getICEServers(): Promise<ICEServer[]> {
    try {
      // Import AWS SDK client
      const { KinesisVideoClient, GetSignalingChannelEndpointCommand } = await import('@aws-sdk/client-kinesis-video');
      const { KinesisVideoSignalingClient, GetIceServerConfigCommand } = await import('@aws-sdk/client-kinesis-video-signaling');
      
      // Get signaling channel endpoint for ICE server config
      const kvsClient = new KinesisVideoClient({
        region: this.config.region,
        credentials: this.config.credentials,
      });
      
      const endpointResponse = await kvsClient.send(
        new GetSignalingChannelEndpointCommand({
          ChannelARN: this.config.channelARN,
          SingleMasterChannelEndpointConfiguration: {
            Protocols: ['HTTPS'],
            Role: this.config.role === 'MASTER' ? 'MASTER' : 'VIEWER',
          },
        })
      );
      
      const httpsEndpoint = endpointResponse.ResourceEndpointList?.find(
        ep => ep.Protocol === 'HTTPS'
      );
      
      if (!httpsEndpoint || !httpsEndpoint.ResourceEndpoint) {
        throw new Error('Failed to get HTTPS endpoint for ICE server config');
      }
      
      // Get ICE server configuration
      const signalingClient = new KinesisVideoSignalingClient({
        region: this.config.region,
        credentials: this.config.credentials,
        endpoint: httpsEndpoint.ResourceEndpoint,
      });
      
      const iceConfigResponse = await signalingClient.send(
        new GetIceServerConfigCommand({
          ChannelARN: this.config.channelARN,
        })
      );
      
      // Convert KVS ICE servers to WebRTC format
      const iceServers: ICEServer[] = iceConfigResponse.IceServerList?.map(server => ({
        urls: server.Uris || [],
        username: server.Username,
        credential: server.Password,
      })) || [];
      
      console.log('[KVS] ICE servers configured:', iceServers.length, 'servers');
      
      return iceServers;
    } catch (error) {
      console.error('[KVS] Failed to get ICE servers:', error);
      throw error;
    }
  }

  /**
   * Set up WebRTC signaling handlers
   */
  private setupSignalingHandlers(): void {
    if (!this.signalingClient || !this.peerConnection) {
      throw new Error('Signaling client or peer connection not initialized');
    }
    
    // Handle SDP offers (for viewers)
    this.signalingClient.on('sdpOffer', async (offer: RTCSessionDescriptionInit, remoteClientId: string) => {
      console.log('[KVS] Received SDP offer from:', remoteClientId);
      this.remoteClientId = remoteClientId;
      
      try {
        await this.peerConnection!.setRemoteDescription(offer);
        console.log('[KVS] Set remote description (offer)');
        
        // Create and send answer
        const answer = await this.peerConnection!.createAnswer();
        await this.peerConnection!.setLocalDescription(answer);
        console.log('[KVS] Created SDP answer');
        
        this.signalingClient!.sendSdpAnswer(
          this.peerConnection!.localDescription!,
          remoteClientId
        );
        console.log('[KVS] Sent SDP answer');
      } catch (error) {
        console.error('[KVS] Error handling SDP offer:', error);
        this.onError?.(error as Error);
      }
    });
    
    // Handle SDP answers (for masters)
    this.signalingClient.on('sdpAnswer', async (answer: RTCSessionDescriptionInit, remoteClientId: string) => {
      console.log('[KVS] Received SDP answer from:', remoteClientId);
      this.remoteClientId = remoteClientId;
      
      try {
        await this.peerConnection!.setRemoteDescription(answer);
        console.log('[KVS] Set remote description (answer)');
      } catch (error) {
        console.error('[KVS] Error handling SDP answer:', error);
        this.onError?.(error as Error);
      }
    });
    
    // Handle ICE candidates
    this.signalingClient.on('iceCandidate', async (candidate: RTCIceCandidateInit, remoteClientId: string) => {
      console.log('[KVS] Received ICE candidate from:', remoteClientId);
      
      try {
        await this.peerConnection!.addIceCandidate(candidate);
        console.log('[KVS] Added ICE candidate');
      } catch (error) {
        console.error('[KVS] Error adding ICE candidate:', error);
      }
    });
    
    // Handle signaling client errors
    this.signalingClient.on('error', (error: Error) => {
      console.error('[KVS] Signaling error:', error);
      this.onError?.(error);
    });
    
    // Send local ICE candidates
    this.peerConnection.onicecandidate = (event) => {
      if (event.candidate) {
        console.log('[KVS] Sending ICE candidate');
        
        if (this.config.role === 'MASTER') {
          // Master sends to all viewers
          this.signalingClient!.sendIceCandidate(event.candidate);
        } else if (this.remoteClientId) {
          // Viewer sends to specific master
          this.signalingClient!.sendIceCandidate(event.candidate, this.remoteClientId);
        }
      }
    };
    
    // For masters: Create offer when viewer connects
    if (this.config.role === 'MASTER') {
      this.signalingClient.on('open', async () => {
        console.log('[KVS] Signaling channel opened as Master');
        // Master waits for viewers to connect
        // Offer will be created when viewer sends SDP offer
      });
      
      // When viewer connects, master creates offer
      this.signalingClient.on('sdpOffer', async (_offer: RTCSessionDescriptionInit, _remoteClientId: string) => {
        // This shouldn't happen for master (masters don't receive offers)
        // But handle it gracefully
        console.warn('[KVS] Master received unexpected SDP offer');
      });
    } else {
      // Viewer creates offer when channel opens
      this.signalingClient.on('open', async () => {
        console.log('[KVS] Signaling channel opened as Viewer, creating offer...');
        
        try {
          const offer = await this.peerConnection!.createOffer({
            offerToReceiveAudio: true,
            offerToReceiveVideo: false,
          });
          
          await this.peerConnection!.setLocalDescription(offer);
          console.log('[KVS] Created and set local SDP offer');
          
          this.signalingClient!.sendSdpOffer(this.peerConnection!.localDescription!);
          console.log('[KVS] Sent SDP offer to Master');
        } catch (error) {
          console.error('[KVS] Error creating SDP offer:', error);
          this.onError?.(error as Error);
        }
      });
    }
  }

  /**
   * Set up peer connection event handlers
   */
  private setupConnectionHandlers(): void {
    if (!this.peerConnection) {
      return;
    }
    
    // Connection state changes
    this.peerConnection.onconnectionstatechange = () => {
      const state = this.peerConnection!.connectionState;
      console.log('[KVS] Connection state:', state);
      this.onConnectionStateChange?.(state);
      
      if (state === 'failed' || state === 'closed') {
        console.error('[KVS] Connection failed or closed');
      }
    };
    
    // ICE connection state changes
    this.peerConnection.oniceconnectionstatechange = () => {
      const state = this.peerConnection!.iceConnectionState;
      console.log('[KVS] ICE connection state:', state);
      this.onICEConnectionStateChange?.(state);
      
      if (state === 'failed') {
        console.error('[KVS] ICE connection failed - may need TURN relay');
      } else if (state === 'connected' || state === 'completed') {
        console.log('[KVS] ICE connection established successfully');
      }
    };
    
    // ICE gathering state
    this.peerConnection.onicegatheringstatechange = () => {
      console.log('[KVS] ICE gathering state:', this.peerConnection!.iceGatheringState);
    };
    
    // Signaling state
    this.peerConnection.onsignalingstatechange = () => {
      console.log('[KVS] Signaling state:', this.peerConnection!.signalingState);
    };
  }

  /**
   * Get connection state
   */
  getConnectionState(): RTCPeerConnectionState | null {
    return this.peerConnection?.connectionState || null;
  }

  /**
   * Get ICE connection state
   */
  getICEConnectionState(): RTCIceConnectionState | null {
    return this.peerConnection?.iceConnectionState || null;
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    const connState = this.peerConnection?.connectionState;
    return connState === 'connected';
  }

  /**
   * Mute local audio (for speakers)
   */
  mute(): void {
    if (this.localStream) {
      this.localStream.getAudioTracks().forEach(track => {
        track.enabled = false;
      });
      console.log('[KVS] Audio muted');
    }
  }

  /**
   * Unmute local audio (for speakers)
   */
  unmute(): void {
    if (this.localStream) {
      this.localStream.getAudioTracks().forEach(track => {
        track.enabled = true;
      });
      console.log('[KVS] Audio unmuted');
    }
  }

  /**
   * Set volume for local audio tracks
   */
  setVolume(volume: number): void {
    // Note: Volume control for MediaStreamTrack is limited
    // Actual volume control should be done at the audio element level
    console.log('[KVS] Volume control:', volume);
    // Store for application-level volume control
  }

  /**
   * Cleanup resources
   */
  cleanup(): void {
    console.log('[KVS] Cleaning up WebRTC resources...');
    
    // Stop local media tracks
    if (this.localStream) {
      this.localStream.getTracks().forEach(track => {
        track.stop();
        console.log('[KVS] Stopped media track');
      });
      this.localStream = null;
    }
    
    // Close peer connection
    if (this.peerConnection) {
      this.peerConnection.close();
      console.log('[KVS] Closed peer connection');
      this.peerConnection = null;
    }
    
    // Close signaling client
    if (this.signalingClient) {
      this.signalingClient.close();
      console.log('[KVS] Closed signaling client');
      this.signalingClient = null;
    }
    
    this.remoteClientId = null;
  }

  /**
   * Generate unique client ID for viewer
   */
  private generateClientId(): string {
    return `viewer-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }
}
