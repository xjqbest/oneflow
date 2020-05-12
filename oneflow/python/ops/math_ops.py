from __future__ import absolute_import

import os
import oneflow.python.framework.compile_context as compile_context
import oneflow.python.framework.remote_blob as remote_blob_util
import oneflow.python.framework.id_util as id_util
import oneflow.core.operator.op_conf_pb2 as op_conf_util
import oneflow.core.register.logical_blob_id_pb2 as logical_blob_id_util

from oneflow.python.oneflow_export import oneflow_export

import oneflow as flow
import os

@oneflow_export("math.add")
def add(x, y, name=None):
    if isinstance(x, (int, float)):
        return scalar_add(y, x, name)
    elif isinstance(y, (int, float)):
        return scalar_add(x, y, name)
    elif x.static_shape == y.static_shape and x.batch_axis == y.batch_axis:
        return element_wise_add(x, y, name)
    elif x.static_shape == (1,):
        return scalar_add_by_tensor(y, x, name)
    elif y.static_shape == (1,):
        return scalar_add_by_tensor(x, y, name)
    else:
        return broadcast_add(x, y, name)

@oneflow_export("math.add_n")
def add_n(inputs, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("AddN_"),
    )
    assert len(inputs) > 1
    for blob in inputs:
        getattr(op_conf.add_conf, "in").append(blob.logical_blob_name)
    op_conf.add_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)

@oneflow_export("math.subtract")
def subtract(x, y, name=None):
    if isinstance(x, (int, float)):
        return scalar_add(-1 * y, x, name)
    elif isinstance(y, (int, float)):
        return scalar_add(x, -1 * y, name)
    elif x.static_shape == y.static_shape:
        # TODO: add element-wise op
        return broadcast_sub(x, y, name)
    elif x.static_shape == (1, ):
        return scalar_sub_by_tensor(y, x, name)
    elif y.static_shape == (1, ):
        return scalar_sub_by_tensor(x, y, name)
    else:
        return broadcast_sub(x, y, name)


@oneflow_export("math.multiply")
def multiply(x, y, name=None):
    if isinstance(x, (int, float)):
        return scalar_mul(y, x, name)
    elif isinstance(y, (int, float)):
        return scalar_mul(x, y, name)
    elif x.static_shape == y.static_shape and x.batch_axis == y.batch_axis:
        return element_wise_mul(x, y, name)
    elif x.static_shape == (1, ):
        return scalar_mul_by_tensor(y, x, name)
    elif y.static_shape == (1, ):
        return scalar_mul_by_tensor(x, y, name)
    else:
        return broadcast_mul(x, y, name)


@oneflow_export("math.divide")
def divide(x, y, name=None):
    if isinstance(x, (int, float)):
        raise NotImplementedError
    elif isinstance(y, (int, float)):
        raise NotImplementedError
    elif x.static_shape == y.static_shape:
        # TODO: add element-wise op
        return broadcast_div(x, y, name)
    elif x.static_shape == (1, ):
        return scalar_div_by_tensor(y, x, name)
    elif y.static_shape == (1, ):
        return scalar_div_by_tensor(x, y, name)
    else:
        return broadcast_div(x, y, name)


@oneflow_export("math.mod")
def floor_mod(x, y, name=None):
    if isinstance(x, (int, float)):
        raise NotImplementedError
    elif isinstance(y, (int, float)):
        raise NotImplementedError
    elif x.static_shape == y.static_shape:
        # TODO: add element-wise op
        return broadcast_floor_mod(x, y, name)
    else:
        return broadcast_floor_mod(x, y, name)


def scalar_add(x, operand, name=None):
    if name is None:
        name = id_util.UniqueStr("ScalarAdd_")
    if os.getenv("ENABLE_USER_OP") == 'True':
        builder = (flow.user_op_builder(name)
            .Op("scalar_add")
            .Input("in", [x])
            .Output("out")
            )
        if isinstance(operand, int):
            builder = (builder.SetAttr("has_int_operand", True, "AttrTypeBool")
                .SetAttr("has_float_operand", False, "AttrTypeBool")
                .SetAttr("int_operand", operand, "AttrTypeInt64")
                .SetAttr("float_operand", 0.0, "AttrTypeDouble"))
        elif isinstance(operand, float):
            builder = (builder.SetAttr("has_int_operand", False, "AttrTypeBool")
                .SetAttr("has_float_operand", True, "AttrTypeBool")
                .SetAttr("int_operand", 0, "AttrTypeInt64")
                .SetAttr("float_operand", operand, "AttrTypeDouble"))
        return (builder
            .Build()
            .InferAndTryRun()
            .RemoteBlobList()[0])
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf, "name", name
    )
    setattr(op_conf.scalar_add_conf, "in", x.logical_blob_name)
    if isinstance(operand, int):
        op_conf.scalar_add_conf.int_operand = operand
    elif isinstance(operand, float):
        op_conf.scalar_add_conf.float_operand = operand
    op_conf.scalar_add_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)

def scalar_add_by_tensor(x, scalar, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf, "name", name if name is not None else id_util.UniqueStr("ScalarAddByTensor_")
    )
    setattr(op_conf.scalar_add_by_tensor_conf, "in", x.logical_blob_name)
    setattr(op_conf.scalar_add_by_tensor_conf, "scalar", scalar.logical_blob_name)
    op_conf.scalar_add_by_tensor_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)

def element_wise_add(x, y, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("ElementWiseAdd_"),
    )
    getattr(op_conf.add_conf, "in").append(x.logical_blob_name)
    getattr(op_conf.add_conf, "in").append(y.logical_blob_name)
    op_conf.add_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


def broadcast_add(x, y, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("BroadcastAdd_"),
    )
    op_conf.broadcast_add_conf.a = x.logical_blob_name
    op_conf.broadcast_add_conf.b = y.logical_blob_name
    op_conf.broadcast_add_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


def broadcast_sub(x, y, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("BroadcastSub_"),
    )
    op_conf.broadcast_sub_conf.a = x.logical_blob_name
    op_conf.broadcast_sub_conf.b = y.logical_blob_name
    op_conf.broadcast_sub_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)

def scalar_sub_by_tensor(x, scalar, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf, "name", name if name is not None else id_util.UniqueStr("ScalarSubByTensor_")
    )
    setattr(op_conf.scalar_sub_by_tensor_conf, "in", x.logical_blob_name)
    setattr(op_conf.scalar_sub_by_tensor_conf, "scalar", scalar.logical_blob_name)
    op_conf.scalar_sub_by_tensor_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)

def element_wise_mul(x, y, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("ElementWiseMul_"),
    )
    setattr(op_conf.multiply_conf, "in_0", x.logical_blob_name)
    setattr(op_conf.multiply_conf, "in_1", y.logical_blob_name)
    op_conf.multiply_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


def broadcast_mul(x, y, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("BroadcastMul_"),
    )
    op_conf.broadcast_mul_conf.a = x.logical_blob_name
    op_conf.broadcast_mul_conf.b = y.logical_blob_name
    op_conf.broadcast_mul_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


def scalar_mul(x, operand, name=None):
    if name is None:
        name = id_util.UniqueStr("ScalarMul_")
    if os.getenv("ENABLE_USER_OP") == 'True':
        builder = (flow.user_op_builder(name)
            .Op("scalar_mul")
            .Input("in", [x])
            .Output("out")
            )
        if isinstance(operand, int):
            builder = (builder.SetAttr("has_int_operand", True, "AttrTypeBool")
                .SetAttr("has_float_operand", False, "AttrTypeBool")
                .SetAttr("int_operand", operand, "AttrTypeInt64")
                .SetAttr("float_operand", 0.0, "AttrTypeDouble"))
        elif isinstance(operand, float):
            builder = (builder.SetAttr("has_int_operand", False, "AttrTypeBool")
                .SetAttr("has_float_operand", True, "AttrTypeBool")
                .SetAttr("int_operand", 0, "AttrTypeInt64")
                .SetAttr("float_operand", operand, "AttrTypeDouble"))
        return (builder
            .Build()
            .InferAndTryRun()
            .RemoteBlobList()[0])
    else:
        op_conf = op_conf_util.OperatorConf()
        setattr(
            op_conf, "name", name
        )
        setattr(op_conf.scalar_mul_conf, "in", x.logical_blob_name)
        if isinstance(operand, int):
            op_conf.scalar_mul_conf.int_operand = operand
        elif isinstance(operand, float):
            op_conf.scalar_mul_conf.float_operand = operand
        op_conf.scalar_mul_conf.out = "out"
        compile_context.CurJobAddOp(op_conf)
        lbi = logical_blob_id_util.LogicalBlobId()
        lbi.op_name = op_conf.name
        lbi.blob_name = "out"
        return remote_blob_util.RemoteBlob(lbi)

def scalar_mul_by_tensor(x, scalar, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf, "name", name if name is not None else id_util.UniqueStr("ScalarMulByTensor_")
    )
    setattr(op_conf.scalar_mul_by_tensor_conf, "in", x.logical_blob_name)
    setattr(op_conf.scalar_mul_by_tensor_conf, "scalar", scalar.logical_blob_name)
    op_conf.scalar_mul_by_tensor_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)

def broadcast_div(x, y, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("BroadcastDiv_"),
    )
    op_conf.broadcast_div_conf.a = x.logical_blob_name
    op_conf.broadcast_div_conf.b = y.logical_blob_name
    op_conf.broadcast_div_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)

def scalar_div_by_tensor(x, scalar, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf, "name", name if name is not None else id_util.UniqueStr("ScalarDivByTensor_")
    )
    setattr(op_conf.scalar_div_by_tensor_conf, "in", x.logical_blob_name)
    setattr(op_conf.scalar_div_by_tensor_conf, "scalar", scalar.logical_blob_name)
    op_conf.scalar_div_by_tensor_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


def broadcast_floor_mod(x, y, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("BroadcastMod_"),
    )
    op_conf.broadcast_floor_mod_conf.a = x.logical_blob_name
    op_conf.broadcast_floor_mod_conf.b = y.logical_blob_name
    op_conf.broadcast_floor_mod_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


@oneflow_export("math.tanh", "keras.activations.tanh")
def tanh(x, name=None):
    if os.getenv("ENABLE_USER_OP") != 'True':
        op_conf = op_conf_util.OperatorConf()
        setattr(op_conf, "name", name if name is not None else id_util.UniqueStr("TanH_"))
        setattr(op_conf.tanh_conf, "in", x.logical_blob_name)
        setattr(op_conf.tanh_conf, "out", "out")
        compile_context.CurJobAddOp(op_conf)
        lbi = logical_blob_id_util.LogicalBlobId()
        lbi.op_name = op_conf.name
        lbi.blob_name = "out"
        return remote_blob_util.RemoteBlob(lbi)

    return (
        flow.user_op_builder(name if name is not None else id_util.UniqueStr("TanH_"))
        .Op("tanh")
        .Input("in", [x])
        .Output("out")
        .Build()
        .InferAndTryRun()
        .RemoteBlobList()[0]
    )


@oneflow_export("math.gelu", "keras.activations.gelu")
def gelu(x, name=None):
    if os.getenv("ENABLE_USER_OP") == 'True':
        return (
            flow.user_op_builder(name if name is not None else id_util.UniqueStr("Gelu_"))
            .Op("gelu")
            .Input("in", [x])
            .Output("out")
            .Build()
            .InferAndTryRun()
            .RemoteBlobList()[0]
        )
    else:
        op_conf = op_conf_util.OperatorConf()
        setattr(op_conf, "name", name if name is not None else id_util.UniqueStr("Gelu_"))
        setattr(op_conf.gelu_conf, "in", x.logical_blob_name)
        setattr(op_conf.gelu_conf, "out", "out")
        compile_context.CurJobAddOp(op_conf)
        lbi = logical_blob_id_util.LogicalBlobId()
        lbi.op_name = op_conf.name
        lbi.blob_name = "out"
        return remote_blob_util.RemoteBlob(lbi)


@oneflow_export("math.relu", "nn.relu")
def relu(x, name=None):
    if os.getenv("ENABLE_USER_OP") != 'True':
        op_conf = op_conf_util.OperatorConf()
        setattr(op_conf, "name", name if name is not None else id_util.UniqueStr("Relu_"))
        setattr(op_conf.relu_conf, "in", x.logical_blob_name)
        setattr(op_conf.relu_conf, "out", "out")
        compile_context.CurJobAddOp(op_conf)
        lbi = logical_blob_id_util.LogicalBlobId()
        lbi.op_name = op_conf.name
        lbi.blob_name = "out"
        return remote_blob_util.RemoteBlob(lbi)

    return (
        flow.user_op_builder(name if name is not None else id_util.UniqueStr("Relu_"))
        .Op("relu")
        .Input("in", [x])
        .Output("out")
        .Build()
        .InferAndTryRun()
        .RemoteBlobList()[0]
    )


@oneflow_export("math.sigmoid")
def sigmoid(x, name=None):
    if os.getenv("ENABLE_USER_OP") != 'True':
        op_conf = op_conf_util.OperatorConf()
        setattr(
            op_conf, "name", name if name is not None else id_util.UniqueStr("Sigmoid_")
        )
        setattr(op_conf.sigmoid_conf, "in", x.logical_blob_name)
        setattr(op_conf.sigmoid_conf, "out", "out")
        compile_context.CurJobAddOp(op_conf)
        lbi = logical_blob_id_util.LogicalBlobId()
        lbi.op_name = op_conf.name
        lbi.blob_name = "out"
        return remote_blob_util.RemoteBlob(lbi)

    return (
        flow.user_op_builder(name if name is not None else id_util.UniqueStr("Sigmoid_"))
        .Op("sigmoid")
        .Input("in", [x])
        .Output("out")
        .Build()
        .InferAndTryRun()
        .RemoteBlobList()[0]
    )

@oneflow_export("math.unsorted_segment_sum", "unsorted_segment_sum")
def unsorted_segment_sum(data, segment_ids, num_segments, axis=0, name=None):
    if name is None:
        name = id_util.UniqueStr("UnsortedSegmentSum_")
    op_conf = op_conf_util.OperatorConf()
    op_conf.name = name
    op_conf.unsorted_segment_sum_conf.data = data.logical_blob_name
    op_conf.unsorted_segment_sum_conf.segment_ids = segment_ids.logical_blob_name
    op_conf.unsorted_segment_sum_conf.num_segments = num_segments
    op_conf.unsorted_segment_sum_conf.axis = axis
    op_conf.unsorted_segment_sum_conf.out = "out"

    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


@oneflow_export("math.unsorted_segment_sum_like", "unsorted_segment_sum_like")
def unsorted_segment_sum_like(data, segment_ids, like, axis=0, name=None):
    if name is None:
        name = id_util.UniqueStr("UnsortedSegmentSumLike_")
    op_conf = op_conf_util.OperatorConf()
    op_conf.name = name
    op_conf.unsorted_segment_sum_like_conf.data = data.logical_blob_name
    op_conf.unsorted_segment_sum_like_conf.segment_ids = segment_ids.logical_blob_name
    op_conf.unsorted_segment_sum_like_conf.like = like.logical_blob_name
    op_conf.unsorted_segment_sum_like_conf.axis = axis
    op_conf.unsorted_segment_sum_like_conf.out = "out"

    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


@oneflow_export("math.unsorted_batch_segment_sum", "unsorted_batch_segment_sum")
def unsorted_batch_segment_sum(data, segment_ids, num_segments, name=None):
    if name is None:
        name = id_util.UniqueStr("UnsortedBatchSegmentSum_")

    op_conf = op_conf_util.OperatorConf()
    op_conf.name = name
    op_conf.unsorted_batch_segment_sum_conf.data = data.logical_blob_name
    op_conf.unsorted_batch_segment_sum_conf.segment_ids = segment_ids.logical_blob_name
    op_conf.unsorted_batch_segment_sum_conf.num_segments = num_segments
    op_conf.unsorted_batch_segment_sum_conf.out = "out"

    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


@oneflow_export("math.sqrt")
def sqrt(x, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(op_conf, "name", name if name is not None else id_util.UniqueStr("Sqrt_"))
    setattr(op_conf.sqrt_conf, "in", x.logical_blob_name)
    setattr(op_conf.sqrt_conf, "out", "out")
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


@oneflow_export("math.rsqrt")
def rsqrt(x, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(op_conf, "name", name if name is not None else id_util.UniqueStr("Rsqrt_"))
    setattr(op_conf.rsqrt_conf, "in", x.logical_blob_name)
    setattr(op_conf.rsqrt_conf, "out", "out")
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


@oneflow_export("cast")
def cast(x, dtype, name=None):
    if x.dtype == dtype:
        return x
    op_conf = op_conf_util.OperatorConf()
    setattr(op_conf, "name", name if name is not None else id_util.UniqueStr("Cast_"))
    setattr(op_conf.cast_conf, "in", x.logical_blob_name)
    setattr(op_conf.cast_conf, "data_type", dtype)
    setattr(op_conf.cast_conf, "out", "out")
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


@oneflow_export("math.naive_logical_and")
def naive_logical_and(lhs, rhs, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf, "name", name if name is not None else id_util.UniqueStr("LogicalAnd_")
    )
    setattr(op_conf.logical_and_conf, "lhs", lhs.logical_blob_name)
    setattr(op_conf.logical_and_conf, "rhs", rhs.logical_blob_name)
    setattr(op_conf.logical_and_conf, "out", "out")
    compile_context.CurJobAddOp(op_conf)
    out_lbi = logical_blob_id_util.LogicalBlobId()
    setattr(out_lbi, "op_name", op_conf.name)
    setattr(out_lbi, "blob_name", "out")
    return remote_blob_util.RemoteBlob(out_lbi)


@oneflow_export("math.equal")
def equal(x, y, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("BroadcastEqual_"),
    )
    op_conf.broadcast_equal_conf.a = x.logical_blob_name
    op_conf.broadcast_equal_conf.b = y.logical_blob_name
    op_conf.broadcast_equal_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


@oneflow_export("math.not_equal")
def not_equal(x, y, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("BroadcastNotEqual_"),
    )
    op_conf.broadcast_not_equal_conf.a = x.logical_blob_name
    op_conf.broadcast_not_equal_conf.b = y.logical_blob_name
    op_conf.broadcast_not_equal_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


@oneflow_export("math.less")
def less(x, y, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("BroadcastLessThan_"),
    )
    op_conf.broadcast_less_than_conf.a = x.logical_blob_name
    op_conf.broadcast_less_than_conf.b = y.logical_blob_name
    op_conf.broadcast_less_than_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


@oneflow_export("math.less_equal")
def less_equal(x, y, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("BroadcastLessEqual_"),
    )
    op_conf.broadcast_less_equal_conf.a = x.logical_blob_name
    op_conf.broadcast_less_equal_conf.b = y.logical_blob_name
    op_conf.broadcast_less_equal_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


@oneflow_export("math.greater")
def greater(x, y, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("BroadcastGreaterThan_"),
    )
    op_conf.broadcast_greater_than_conf.a = x.logical_blob_name
    op_conf.broadcast_greater_than_conf.b = y.logical_blob_name
    op_conf.broadcast_greater_than_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


@oneflow_export("math.greater_equal")
def greater_equal(x, y, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("BroadcastGreaterEqual_"),
    )
    op_conf.broadcast_greater_equal_conf.a = x.logical_blob_name
    op_conf.broadcast_greater_equal_conf.b = y.logical_blob_name
    op_conf.broadcast_greater_equal_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


@oneflow_export("math.logical_and")
def logical_and(x, y, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("BroadcastLogicalAnd_"),
    )
    op_conf.broadcast_logical_and_conf.a = x.logical_blob_name
    op_conf.broadcast_logical_and_conf.b = y.logical_blob_name
    op_conf.broadcast_logical_and_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


@oneflow_export("math.minimum")
def broadcast_min(x, y, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("BroadcastMin_"),
    )
    op_conf.broadcast_min_conf.a = x.logical_blob_name
    op_conf.broadcast_min_conf.b = y.logical_blob_name
    op_conf.broadcast_min_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


@oneflow_export("math.maximum")
def broadcast_max(x, y, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("BroadcastMax_"),
    )
    op_conf.broadcast_max_conf.a = x.logical_blob_name
    op_conf.broadcast_max_conf.b = y.logical_blob_name
    op_conf.broadcast_max_conf.out = "out"
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)


@oneflow_export("math.reduced_shape_elem_cnt")
def elem_cnt(input_blob, axis=None, dtype=None, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(op_conf, "name", name if name is not None else id_util.UniqueStr("ShapeElemCnt_"))
    op_conf.shape_elem_cnt_conf.x = input_blob.logical_blob_name
    if axis is None:
        op_conf.shape_elem_cnt_conf.exclude_axis_conf.SetInParent()
    else:
        assert isinstance(axis, (tuple, list))
        op_conf.shape_elem_cnt_conf.include_axis_conf.axis.extend(axis)
    if dtype is not None:
        op_conf.shape_elem_cnt_conf.data_type = dtype
    op_conf.shape_elem_cnt_conf.y = "y"
    compile_context.CurJobAddOp(op_conf)
    out_lbi = logical_blob_id_util.LogicalBlobId()
    out_lbi.op_name = op_conf.name
    out_lbi.blob_name = "y"
    return remote_blob_util.RemoteBlob(out_lbi)

@oneflow_export('math.square')
def square(x, name=None):
    op_conf = op_conf_util.OperatorConf()
    setattr(
        op_conf,
        "name",
        name if name is not None else id_util.UniqueStr("Square_"),
    )
    setattr(op_conf.square_conf, "in", x.logical_blob_name)
    setattr(op_conf.square_conf, "out", "out")
    compile_context.CurJobAddOp(op_conf)
    lbi = logical_blob_id_util.LogicalBlobId()
    lbi.op_name = op_conf.name
    lbi.blob_name = "out"
    return remote_blob_util.RemoteBlob(lbi)

@oneflow_export("math.top_k")
def top_k(input, k=1, sorted=True, name=None):
    return (
        flow.user_op_builder(name if name is not None else id_util.UniqueStr("TopK_"))
        .Op("top_k")
        .Input("in", [input])
        .Output("out")
        .SetAttr("k", k, "AttrTypeInt32",)
        .SetAttr("sorted", sorted, "AttrTypeBool",)
        .Build()
        .InferAndTryRun()
        .RemoteBlobList()[0]
    )

@oneflow_export("math.argmax")
def argmax(input, name=None):
    return (
        flow.user_op_builder(name if name is not None else id_util.UniqueStr("ArgMax_"))
        .Op("argmax")
        .Input("in", [input])
        .Output("out")
        .Build()
        .InferAndTryRun()
        .RemoteBlobList()[0]
    )

@oneflow_export("math.broadcast_to_compatible_with", "broadcast_to_compatible_with")
def broadcast_to_compatible_with(x, compatible, name=None):
    assert isinstance(compatible, (list, tuple))
    if name is None:
        name = id_util.UniqueStr("BroadcastToCompatibleWith_")

    op_conf = op_conf_util.OperatorConf()
    setattr(op_conf, "name", name)
    setattr(op_conf.broadcast_to_compatible_with_conf, "x", x.logical_blob_name)
    setattr(op_conf.broadcast_to_compatible_with_conf, "y", "y")
    op_conf.broadcast_to_compatible_with_conf.compatible.extend(
        [cp.logical_blob_name for cp in compatible]
    )
    compile_context.CurJobAddOp(op_conf)

    ret_lbi = logical_blob_id_util.LogicalBlobId()
    ret_lbi.op_name = op_conf.name
    ret_lbi.blob_name = "y"
    return remote_blob_util.RemoteBlob(ret_lbi)


@oneflow_export("math.clip_by_value", "clip_by_value", "clip_by_scalar", "clip", "clamp")
def clip_by_value(values, min_value=None, max_value=None, name=None):
    if name is None:
        name = id_util.UniqueStr("ClipByValue_")

    if min_value is not None and max_value is not None:
        op_builder = (
            flow.user_op_builder(name)
            .Op("clip_by_scalar")
            .SetAttr("floating_min", float(min_value), "AttrTypeDouble")
            .SetAttr("integral_min", int(min_value), "AttrTypeInt64")
            .SetAttr("floating_max", float(max_value), "AttrTypeDouble")
            .SetAttr("integral_max", int(max_value), "AttrTypeInt64")
        )
    elif min_value is not None:
        op_builder = (
            flow.user_op_builder(name)
            .Op("clip_by_scalar_min")
            .SetAttr("floating_min", float(min_value), "AttrTypeDouble")
            .SetAttr("integral_min", int(min_value), "AttrTypeInt64")
        )
    elif max_value is not None:
        op_builder = (
            flow.user_op_builder(name)
            .Op("clip_by_scalar_max")
            .SetAttr("floating_max", float(max_value), "AttrTypeDouble")
            .SetAttr("integral_max", int(max_value), "AttrTypeInt64")
        )
    else:
        raise ValueError("min_value and max_value cannot be None at the same time")

    return op_builder.Input("x", [values]).Output("y").Build().InferAndTryRun().RemoteBlobList()[0]


@oneflow_export("math.l2_normalize")
def l2_normalize(input, axis=None, epsilon=1e-12, name=None):
    if axis < 0: axis += len(input.shape)
    assert axis >=0 and axis < len(input.shape)
    y, square_x_sum = (
        flow.user_op_builder(name if name is not None else id_util.UniqueStr("L2Normalize_"))
        .Op("l2_normalize")
        .Input("x", [input])
        .Output("y")
        .Output("square_x_sum")
        .SetAttr("axis", int(axis), "AttrTypeInt32")
        .SetAttr("epsilon", float(epsilon), "AttrTypeFloat")
        .Build()
        .InferAndTryRun()
        .RemoteBlobList()
    )
    return y


@oneflow_export("math.squared_difference")
def squared_difference(x, y, name=None):
    name_subtract, name_square = None, None
    if name is not None:
        name_subtract = name + "_subtract"
        name_square = name + "_square"
    return flow.math.square(flow.math.subtract(x, y, name_subtract), name_square)

 
@oneflow_export("math.polyval")
def polyval(coeffs, x, name=None):
    if name is None:
        name = id_util.UniqueStr("Polyval_")
    if not isinstance(coeffs, list):
        raise ValueError("Argument coeffs must be list type "
                         "found {}".format(type(coeffs)))
    if len(coeffs) < 1:
        return flow.zeros_like(x, name = name)
    p = flow.zeros_like(x, name = name)
    for c in coeffs:
        p = flow.math.add(c,flow.math.multiply(p,x))
    return p

