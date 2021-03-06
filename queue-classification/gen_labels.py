#!/usr/bin/env python3
import json
import numpy as np
import cv2
import mrcnn.config
import mrcnn.utils
from mrcnn.model import MaskRCNN

from os.path import dirname
import os

QUEUETIME_DIR = dirname(dirname(os.path.abspath(__file__)))

ROOT_DIR = dirname(os.path.abspath(__file__))
MODEL_DIR = ROOT_DIR + '/model_data'
COCO_MODEL_PATH = os.path.join(ROOT_DIR, "mask_rcnn_coco.h5")
PERSON_CATEGORY_ID = 1

# Borrowed heavily from: https://medium.com/@ageitgey/snagging-parking-spaces-with-mask-r-cnn-and-python-955f2231c400``

def assert_model_downloaded():
    "Downloads the pre-trained coco model if need be"
    if not os.path.exists(COCO_MODEL_PATH):
        mrcnn.utils.download_trained_weights(COCO_MODEL_PATH)
        assert os.path.exists(COCO_MODEL_PATH), "Download failed"


# Configuration that will be used by the Mask-RCNN library
class MaskRCNNConfig(mrcnn.config.Config):
    NAME = "coco_pretrained_model_config"
    IMAGES_PER_GPU = 1
    GPU_COUNT = 1
    NUM_CLASSES = 1 + 80  # COCO dataset has 80 classes + one background class
    DETECTION_MIN_CONFIDENCE = 0.6


def evaluate_video(video_path):
    assert os.path.exists(video_path), "Video does not exist"
    vidstream = cv2.VideoCapture(video_path)

    model = MaskRCNN(mode='inference', model_dir=MODEL_DIR, config=MaskRCNNConfig())
    model.load_weights(COCO_MODEL_PATH, by_name=True)

    frame_annotations = []

    frame_num = -1
    while vidstream.isOpened():
        frame_num += 1

        success, frame = vidstream.read()
        if not success:
            # Stream is empty
            break

        # Convert from brg to rgb
        frame = frame[:,:,::-1]

        # Run through the model, grabbing the only frame
        result = model.detect([frame], verbose=0)[0]

        this_frame_annotations = []
        for index, class_id in enumerate(result['class_ids']):
            if class_id == PERSON_CATEGORY_ID:
                # Convert bounding box into [x, y, width, height]
                # from [x1, y1, x2, y2]
                box = result['rois'][index].tolist()
                assert box[0] <= box[2], "y2 < y1 on index %d in frame %d" % (frame_num, index)
                assert box[1] <= box[3], "x2 < x1 on index %d in frame %d" % (frame_num, index)
                wh_box = [box[1], box[0], box[3] - box[1], box[2] - box[0]]
                ann = {
                    'bbox': wh_box,
                    'score': float(result['scores'][index]),
                    'index': index
                }
                this_frame_annotations.append(ann)

        frame_annotations.append(this_frame_annotations)

    vidstream.release()
    return frame_annotations


if __name__ == '__main__':
    import argparse
    from pathlib import Path

    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--video-path", type=Path, help="Path to input video")
    ap.add_argument("-o", "--output", type=Path, help="Path to output file")
    arguments = vars(ap.parse_args())

    assert_model_downloaded()
    frame_annotations = evaluate_video(str(arguments["video_path"]))

    with open(str(arguments["output"]), 'w') as filepointer:
        json.dump(frame_annotations, filepointer)
