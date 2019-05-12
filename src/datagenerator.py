import keras
import numpy as np
from abc import ABC, abstractmethod
from math import ceil, floor

from QueueTimeNet import POS_SCORE, POS_BOX_CENTER_X, POS_BOX_CENTER_Y, POS_BOX_WIDTH, POS_BOX_HEIGHT

# Help from https://stanford.edu/~shervine/blog/keras-how-to-generate-data-on-the-fly
# in this file

class DataGenerator(keras.utils.Sequence, ABC):
    """
    img_width: final width of the imgs as passed out
    img_height: final height of the imgs
    """
    def __init__(self,
                 img_width,
                 img_height,
                 cell_height,
                 cell_width,
                 img_ids,
                 bounding_box_count=1,
                 intersection_threshold=0.7
                 batch_size=20,
    ):
        self.img_width = img_width
        self.img_height = img_height
        self.cell_width = cell_width
        self.cell_height = cell_height
        self.bounding_box_count = bounding_box_count
        self.img_ids = img_ids
        self.intersection_threshold = intersection_threshold

        self.PADDED_SIZE = 640

        self.DEFAULT_LOCATION = 0
        self.NO_OBJECT_WEIGHT = 0
        self.HAS_OBJECT_WEIGHT = 1

    def __len__(self):
        'Number of batches per epoch'
        return floor(len(self.img_ids) / self.batch_size)

    @abstractmethod
    def get_img(self, img_id):
        raise NotImplementedError

    @abstractmethod
    def get_annotations(self, img_id):
        """
        Procedure:
         get_annotations
        Purpose:
         return the annotations for a given image id
        Parameters:
         img_id: int - the image id to get annotations for
        Produces:
         annotations: [{'bbox': [int]}]
        Preconditions:
         No additional
        Postconditions:

        """
        raise NotImplementedError

    def _intersecion_area(rect1_ul, rect1_dims, rect2_ul, rect2_dims):
        """
        Procedure:
         _intersection_area
        Purpose:
         find the area of the intersection of two rectangles
        Paramaters:
         rect1_ul: (number, number) - the coordinates of the upper left hand
                                      corner of the first rectangle, in the
                                      form (x,y)
         rect1_dims: (number, number) - the width and height, in order,
                                        of the first rectangle
         rect2_ul: (number, number) - the coordinates of the upper left hand
                                      corner of the second rectangle, in the
                                      form (x,y)
         rect2_dims: (number, number) - the width and height, in order,
                                        of the second rectangle
        Produces:
         area: float - the area of the rectangles' intersection
        Preconditions:
         No additional
        Postconditions:
         If the boxes do not intersect, return 0 as the intersection
        Implementation:
         1. Find the bottom right portion of both rectangles by adding the
            widths and heights to their respective coordinates
         2. Find the upper right and lower left corners of the rectangle that
            forms their intersection. The former is done by finding the further
            of the two upper left corners from the origin in both directions,
            and using said further number. Same goes for the bottom right,
            instead using the closer of them
         3. Calculate the widths and heights from this. If either are
            negitive, pin them to 0 so that the product will be zero.
         43 Return the product of the width and height
        """
        rect1_br = (rect1_ul[0] + rect1_dims[0], rect1_ul[1] + rect1_dims[1])
        rect2_br = (rect2_ul[0] + rect2_dims[0], rect2_ul[1] + rect2_dims[1])

        # find the upper right corner of their intersection:
        intersection_ul = (max(rect1_ul[0], rect2_ul[0]), max(rect1_ul[1], rect2_ul[1]))
        intersection_br = (min(rect1_br[0], rect2_br[0]), min(rect1_br[1], rect2_br[1]))

        intersection_width = max(0,intersection_br[0] - intersection_ul[0])
        intersection_height = max(0,intersection_br[1] - intersection_ul[1])

        return intersection_width * intersection_height

    # Procedure:
    #  gen_training_tensor
    # Purpose:
    #  To generate the ground truth corresponding to a given image.
    # Parameters:
    #  coco: COCO - a coco instance to pull annotation information from
    #  bounding_box_count: int - number of bounding boxes per cell; known as B in YOLO paper
    #    NOTE: Dead paramater for now - only works with one
    #  cell_width: int - the width in pixels of a cell in the image.
    #  cell_height: int - the height in pixels of a cell in the image.
    #  img_id: id - id for the img
    # Produces:
    #  output: tensor[double] - A tensor of training data
    # Preconditions:
    #  coco is initialized with valid data
    #  cell_width < width of image
    #  cell_height < height of image
    #  bounding_box_count >= 1
    def gen_training_tensor(self, img_id):
        annotations = self.get_annotations(img_id)
        # cell_x_count, how many cells are on horizontal direction, cell_y_count,
        # how many cells are on vertical direction
        cell_x_count = ceil(self.PADDED_SIZE / self.cell_width)
        cell_y_count = ceil(self.PADDED_SIZE / self.cell_height)
        # 5 parameters to each bounding box: Probability, X pos, Y pos, Width, Height
        training_data = np.full((cell_y_count, cell_x_count, self.bounding_box_count * 5), self.DEFAULT_LOCATION)
        training_data = training_data.astype('float32')
        # Set all object probabilities to NO_OBJECT_WEIGHT
        if self.DEFAULT_LOCATION != self.NO_OBJECT_WEIGHT:
            training_data[..., ..., POS_SCORE: :5] = self.NO_OBJECT_WEIGHT

        for annotation in annotations:
            # Calculate the cell that the annotation should match
            bounding_box = annotation['bbox']

            abs_ul_x = bounding_box[0]
            abs_ul_y = bounding_box[1]
            width = bounding_box[2]
            height = bounding_box[3]

            # Find the center of the box in terms of the whole image
            # These values are purposely floats to keep as much information as
            #  possible about the center of the img
            abs_center_x = abs_ul_x + width / 2
            abs_center_y = abs_ul_y + height / 2

            # Calculate the cell the bounding box is centered in
            cell_x_pos = floor(abs_center_x / self.cell_width)
            cell_y_pos = floor(abs_center_y / self.cell_height)

            # Find the center of the box relative to the corner of the cell:
            # ...And put it in terms of the cell size
            rel_center_x = (abs_center_x - (cell_x_pos * self.cell_width)) / self.cell_width
            rel_center_y = (abs_center_y - (cell_y_pos * self.cell_height)) / self.cell_height

            # Find the size of the bounding box relative to the cell
            rel_width = width / self.cell_width
            rel_height = height / self.cell_height

            if training_data[cell_y_pos, cell_x_pos, self.POS_SCORE] != self.NO_OBJECT_WEIGHT:
                logging.warn("Image %d has multiple bounding boxes in cell (%d,%d)" % (
                    img_id,
                    cell_x_pos,
                    cell_y_pos
                ))

            # Set values for the training data
            training_data[cell_y_pos, cell_x_pos, self.POS_BOX_CENTER_X] = rel_center_x
            training_data[cell_y_pos, cell_x_pos, self.POS_BOX_CENTER_Y] = rel_center_y
            training_data[cell_y_pos, cell_x_pos, self.POS_BOX_WIDTH] = rel_width
            training_data[cell_y_pos, cell_x_pos, self.POS_BOX_HEIGHT] = rel_height

            # find the boundings revative to cell_y_pos, cell_x_pos
            x1 = rel_center_x - rel_width / 2  
            x2 = rel_center_x + rel_width / 2
            y1 = rel_center_y - rel_height / 2
            y2 = rel_center_y + rel_height / 2
            
            left_full_x = ceil(x1)
            right_part_x = floor(x2)
            up_full_y = ceil(y1)
            bottom_part_y = floor(y2)

            # full cells first
            if (right_part_x > left_full_x): # there are full coverage cells on x direction
                if (bottom_part_y > up_full_y): #there are full coverage cells on y direction
                    for x in range(left_full_x, right_part_x): #inclusive, exclusive 
                        for y in range(up_full_y,bottom_part_y): 
                            # only set the score, x y w h don't matter in the loss
                            training_data[cell_y_pos + y, cell_x_pos + x, self.POS_SCORE] = self.HAS_OBJECT_WEIGHT
            
            # border cells
            left_part_x = left_full_x - 1
            up_part_y = up_full_y - 1
            left_margin = left_full_x - x1
            right_margin = x2 - right_part_x 
            up_margin = up_full_y - y1
            bottom_margin = y2 - bottom_full_y

            if left_margin > self.intersection_threshold:
                for y in range(up_full_y,bottom_part_y): 
                    # only set the score, x y w h don't matter in the loss
                    training_data[ cell_y_pos + y, left_part_x, self.POS_SCORE] = max(training_data[cell_y_pos + y, left_part_x, self.POS_SCORE], self.HAS_OBJECT_WEIGHT)
                    
                
            if right_margin > self.intersection_threshold: 
                for y in range(up_full_y, bottom_part_y): 
                    # only set the score, x y w h don't matter in the loss
                    training_data[cell_y_pos + y, right_part_x, self.POS_SCORE] = max(training_data[cell_y_pos + y, right_part_x, self.POS_SCORE], self.HAS_OBJECT_WEIGHT)
                    
            if up_margin > self.intersection_threshold:
                for x in range(left_full_x, right_part_x): 
                    # only set the score, x y w h don't matter in the loss
                    training_data[up_part_y, cell_x_pos + x, self.POS_SCORE] = max(training_data[up_part_y, left_part_x + x, self.POS_SCORE], self.HAS_OBJECT_WEIGHT)
                    
            if bottom_margin > self.intersection_threshold:
                for x in range(left_full_x, right_part_x): 
                    # only set the score, x y w h don't matter in the loss
                    training_data[bottom_part_y, cell_x_pos + x, self.POS_SCORE] = max(training_data[bottom_part_y, cell_x_pos + x, self.POS_SCORE], self.HAS_OBJECT_WEIGHT)
                    
            if left_margin*up_margin  > self.intersection_threshold: 
                training_data[up_part_y, left_part_x, self.POS_SCORE] = max(training_data[up_part_y, left_part_x, self.POS_SCORE], self.HAS_OBJECT_WEIGHT)

            if left_margin*bottom_margin  > self.intersection_threshold: 
                training_data[bottom_part_y, left_part_x, self.POS_SCORE] = max(training_data[bottom_part_y, left_part_x, self.POS_SCORE], self.HAS_OBJECT_WEIGHT)

            if right_margin*bottom_margin  > self.intersection_threshold: 
                training_data[bottom_part_y, right_part_x, self.POS_SCORE] = max(training_data[bottom_part_y, right_part_x, self.POS_SCORE], self.HAS_OBJECT_WEIGHT)

            if right_margin*up_margin  > self.intersection_threshold: 
                training_data[up_part_y, right_part_x, self.POS_SCORE] = max(training_data[up_part_y, right_part_x, self.POS_SCORE], self.HAS_OBJECT_WEIGHT)

        return training_data

    def __getitem__(self, index):
        """
        Procedure:
         __getitem__
        Purpose:
         To return a single batch of data
        Parameters: - note that this matches python standards for generators
         index: int - the batch number from the epoch to take
        """
        raise NotImplementedError

from file_management import get_downloaded_ids, get_image, ANNOTATION_FILE
from pycocotools.coco import COCO
from annotations import get_image_annotations

class CocoDataGenerator(DataGenerator):
    def __init__(
            self,
            img_width,
            img_height,
            cell_size
    ):
        self.coco = COCO(ANNOTATION_FILE)
        super().__init__(img_width, img_height, cell_size, get_downloaded_ids())

    # Override
    def get_img(self, img_id):
        return get_image(img_id)

    # Override
    def get_annotations(self, img_id):
        return get_image_annotations(self.coco, img_id)