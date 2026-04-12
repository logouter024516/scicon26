export type TabKey = 'home' | 'live' | 'quick' | 'register' | 'capture';

export interface SummaryDto {
  captureStatus: string;
  totalClips: number;
  addedItems: number;
}

export interface ClipDto {
  clipId: string;
  eventAt: string;
  cameraId: string;
  clipFile?: string;
  thumbFile?: string;
}

export interface HealthDto {
  ok: boolean;
  message: string;
}

export interface CaptureStateDto {
  running: boolean;
  cameraIndex: number;
}

export interface LiveResultDto {
  found: boolean;
  score: number;
  detail: string;
  bboxNorm?: number[] | null;
}

export interface PipelineResultDto {
  stage: 'none' | 'live' | 'quick' | string;
  found: boolean;
  message: string;
  live: LiveResultDto;
  quick: QuickResultDto[];
}

export interface QuickResultDto {
  clipId: string;
  score: number;
  detail: string;
  eventAt?: string;
  cameraId?: string;
  clipFile?: string;
  thumbFile?: string;
}

export interface RegisteredItemDto {
  name: string;
  thumbFile?: string;
  createdAt?: string;
}
