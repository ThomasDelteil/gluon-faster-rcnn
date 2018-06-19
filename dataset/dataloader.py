"""DataLoader utils."""
import numpy as np
from mxnet import nd
from mxnet import context
from mxnet.gluon.data import DataLoader


def default_pad_batchify_fn(data):
    """Collate data into batch, labels are padded to same shape"""
    if isinstance(data[0], nd.NDArray):
        # 2. Stack image.shape.shape.shape(c ,h, w) and im_info.shape(3,)
        if len(data[0].shape) == 3:
            # padding image
            pad_h = max([img.shape[1] for img in data] + [1, ])
            pad_w = max([img.shape[2] for img in data] + [1, ])
            buf = nd.zeros((len(data), data[0].shape[0], pad_h, pad_w), dtype=data[0].dtype)
            for i, img in enumerate(data):
                buf[i][:, :img.shape[1], :img.shape[2]] = img
            return nd.array(buf, dtype=data[0].dtype)
        return nd.stack(*data)
    elif isinstance(data[0], tuple):
        # 1. Collect image, label, im_info batch
        data = zip(*data)
        return [default_pad_batchify_fn(i) for i in data]
    else:
        # 2. Padding label
        data = np.asarray(data)
        pad = max([l.shape[0] for l in data] + [1,])
        buf = np.full((len(data), pad, data[0].shape[-1]), fill_value=-1, dtype=data[0].dtype)
        for i, l in enumerate(data):
            buf[i][:l.shape[0], :] = l
        return nd.array(buf)


def default_mp_pad_batchify_fn(data):
    """Use shared memory for collating data into batch, labels are padded to same shape"""
    if isinstance(data[0], nd.NDArray):
        if len(data[0].shape) == 3:
            # padding image
            pad_h = max([img.shape[1] for img in data] + [1, ])
            pad_w = max([img.shape[2] for img in data] + [1, ])
            buf = nd.zeros((len(data), data[0].shape[0], pad_h, pad_w), dtype=data[0].dtype,
                           ctx=context.Context('cpu_shared', 0))
            for i, img in enumerate(data):
                buf[i][:, :img.shape[1], :img.shape[2]] = img
            return buf
        out = nd.empty((len(data),) + data[0].shape, dtype=data[0].dtype,
                       ctx=context.Context('cpu_shared', 0))
        return nd.stack(*data, out=out)
    elif isinstance(data[0], tuple):
        data = zip(*data)
        return [default_mp_pad_batchify_fn(i) for i in data]
    else:
        data = np.asarray(data)
        batch_size = len(data)
        pad = max([l.shape[0] for l in data] + [1,])
        buf = np.full((batch_size, pad, data[0].shape[-1]), -1, dtype=data[0].dtype)
        for i, l in enumerate(data):
            buf[i][:l.shape[0], :] = l
        return nd.array(buf, ctx=context.Context('cpu_shared', 0))


class DetectionDataLoader(DataLoader):
    """Data loader for detection dataset.


    It loads data batches from a dataset and then apply data
    transformations. It's a subclass of :py:class:`mxnet.gluon.data.DataLoader`,
    and therefore has very simliar APIs.

    The main purpose of the DataLoader is to pad variable length of labels from
    each image, because they have different amount of objects.

    Parameters
    ----------
    dataset : mxnet.gluon.data.Dataset or numpy.ndarray or mxnet.ndarray.NDArray
        The source dataset.
    batch_size : int
        The size of mini-batch.
    shuffle : bool, default False
        If or not randomly shuffle the samples. Often use True for training
        dataset and False for validation/test datasets
    sampler : mxnet.gluon.data.Sampler, default None
        The sampler to use. We should either specify a sampler or enable
        shuffle, not both, because random shuffling is a sampling method.
    last_batch : {'keep', 'discard', 'rollover'}, default is keep
        How to handle the last batch if the batch size does not evenly divide by
        the number of examples in the dataset. There are three options to deal
        with the last batch if its size is smaller than the specified batch
        size.

        - keep: keep it
        - discard: throw it away
        - rollover: insert the examples to the beginning of the next batch
    batch_sampler : mxnet.gluon.data.BatchSampler
        A sampler that returns mini-batches. Do not specify batch_size,
        shuffle, sampler, and last_batch if batch_sampler is specified.
    batchify_fn : callable
        Callback function to allow users to specify how to merge samples
        into a batch.
        Defaults to :py:meth:`gluonvision.data.dataloader.default_pad_batchify_fn`::
            def default_pad_batchify_fn(data):
                if isinstance(data[0], nd.NDArray):
                    return nd.stack(*data)
                elif isinstance(data[0], tuple):
                    data = zip(*data)
                    return [pad_batchify(i) for i in data]
                else:
                    data = np.asarray(data)
                    pad = max([l.shape[0] for l in data])
                    buf = np.full((len(data), pad, data[0].shape[-1]),
                                  -1, dtype=data[0].dtype)
                    for i, l in enumerate(data):
                        buf[i][:l.shape[0], :] = l
                    return nd.array(buf, dtype=data[0].dtype)
    num_workers : int, default 0
        The number of multiprocessing workers to use for data preprocessing.
        If ``num_workers`` = 0, multiprocessing is disabled.
        Otherwise ``num_workers`` multiprocessing worker is used to process data.

    """
    def __init__(self, dataset, batch_size=None, shuffle=False, sampler=None,
                 last_batch=None, batch_sampler=None, batchify_fn=None,
                 num_workers=0):
        if batchify_fn is None:
            if num_workers > 0:
                batchify_fn = default_mp_pad_batchify_fn
            else:
                batchify_fn = default_pad_batchify_fn
        super(DetectionDataLoader, self).__init__(
            dataset, batch_size, shuffle, sampler, last_batch,
            batch_sampler, batchify_fn, num_workers)