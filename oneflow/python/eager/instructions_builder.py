from __future__ import absolute_import

import oneflow.core.vm.instruction_pb2 as instr_util
import oneflow.core.eager.eager_symbol_pb2 as eager_symbol_util
import oneflow.core.operator.op_conf_pb2 as op_conf_util
import oneflow.python.framework.placement_context as placement_ctx
import oneflow.python.framework.c_api_util as c_api_util
import oneflow.python.eager.job_conf_ctx as job_conf_ctx
import oneflow.python.eager.id_cache as id_cache

class InstructionsBuilder(object):
    def __init__(self, id_generator, instruction_list, eager_symbol_list):
        assert isinstance(instruction_list, instr_util.InstructionListProto)
        assert isinstance(eager_symbol_list, eager_symbol_util.EagerSymbolList)
        self.instruction_list_ = instruction_list
        self.eager_symbol_list_ = eager_symbol_list
        self.id_generator_ = id_generator

    def StatelessCall(self, op_conf):
        assert op_conf.HasField('user_conf')
        placement_scope = placement_ctx.PlacementScopeStackTop()
        parallel_conf = placement_scope.default_parallel_conf
        device_tag = placement_scope.default_device_tag
        parallel_conf_sym = self.GetSymbolId4ParallelConf(parallel_conf)
        job_conf_sym = self.GetSymbolId4JobConf(job_conf_ctx.CurrentJobConf())
        op_conf_sym = self._GetOpConfSymbolId(op_conf)
        opkernel_obj = self.GetSharedOpKernelObjectId4ParallelConfSymbolId(parallel_conf_sym)
        input_triples = self._GetInputTriples(op_conf)
        output_triples = self._GetOutputTriples(op_conf, parallel_conf_sym)
        mut2_output_triples = self._GetMut2OutputTriples(op_conf, parallel_conf_sym)
        return self._StatelessCall(device_tag, parallel_conf_sym,
                                   job_conf_sym, op_conf_sym, opkernel_obj,
                                   input_triples, output_triples, mut2_output_triples)

    def GetSymbolId4String(self, string):
        if id_cache.HasSymbolId4String(string): return id_cache.GetSymbolId4String(string)
        symbol_id = self._NewSymbolId4String(string)
        id_cache.SetSymbolId4String(string, symbol_id)
        return symbol_id

    def GetSymbolId4JobConf(self, job_conf):
        if id_cache.HasSymbolId4JobConf(job_conf):
            return id_cache.GetSymbolId4JobConf(job_conf)
        symbol_id = self._NewSymbolId4JobConf(job_conf)
        id_cache.SetSymbolId4JobConf(job_conf, symbol_id)
        return symbol_id

    def GetSymbolId4ParallelConf(self, parallel_conf):
        if id_cache.HasSymbolId4ParallelConf(parallel_conf):
            return id_cache.GetSymbolId4ParallelConf(parallel_conf)
        symbol_id = self._NewSymbolId4ParallelConf(parallel_conf)
        id_cache.SetSymbolId4ParallelConf(parallel_conf, symbol_id)
        return symbol_id

    def GetSharedOpKernelObjectId4ParallelConfSymbolId(self, parallel_conf_sym):
        if id_cache.HasSharedOpKernelObjectId4ParallelConfSymbolId(parallel_conf_sym):
            return id_cache.GetSharedOpKernelObjectId4ParallelConfSymbolId(parallel_conf_sym)
        object_id = self._NewSharedOpKernelObjectId4ParallelConfSymbolId(parallel_conf_sym)
        id_cache.SetSharedOpKernelObjectId4ParallelConfSymbolId(parallel_conf_sym, object_id)
        return object_id

    def _GetOpConfSymbolId(self, op_conf):
        new_op_conf = op_conf_util.OperatorConf()
        new_op_conf.CopyFrom(op_conf)
        # drop unique name to achieve a higher cache hit rate
        new_op_conf.name = new_op_conf.user_conf.op_type_name
        new_op_conf.user_conf.ClearField("input")
        new_op_conf.user_conf.ClearField("output")
        serialized_op_conf = new_op_conf.SerializeToString()
        if id_cache.HasSymbolId4SerializedOpConf(serialized_op_conf):
            return id_cache.GetSymbolId4SerializedOpConf(serialized_op_conf)
        symbol_id = self._NewSymbolId4OpConf(new_op_conf)
        id_cache.SetSymbolId4SerializedOpConf(serialized_op_conf, symbol_id)
        return symbol_id

    def _GetInputTriples(self, op_conf):
        input_triples = []
        for ibn, lbns in op_conf.user_conf.input.items():
            ibn_sym = self.GetSymbolId4String(ibn)
            for i in range(len(lbns.s)):
                in_object_id = id_cache.GetObjectId4Lbn(lbns.s[i])
                input_triples.append((ibn_sym, i, in_object_id))
        return input_triples

    def _GetOutputTriples(self, op_conf, parallel_conf_sym):
        output_triples = []
        for obn, lbns in op_conf.user_conf.output.items():
            obn_sym = self.GetSymbolId4String(obn)
            for i in range(len(lbns.s)):
                out_object_id = self._NewBlobObjectId(parallel_conf_sym)
                id_cache.SetObjectId4Lbn(lbns.s[i], out_object_id)
                output_triples.append((obn_sym, i, out_object_id))
        return output_triples

    def _GetMut2OutputTriples(self, op_conf, parallel_conf_sym):
        mut2_output_triples = []
        # TODO(lixinqi)
        return mut2_output_triples

    def _NewSymbolId4String(self, string):
        symbol_id = self._NewSymbolId()
        self._InitStringSymbol(symbol_id, string)
        return symbol_id

    def _NewSymbolId4ParallelConf(self, parallel_conf):
        symbol_id = self.id_generator_.NewSymbolId()
        self._NewParallelConfSymbol(symbol_id, parallel_conf)
        return symbol_id

    def _NewSymbolId4JobConf(self, job_conf):
        symbol_id = self._NewSymbolId()
        self._InitJobConfSymbol(symbol_id, job_conf)
        return symbol_id

    def _NewSymbolId4OpConf(self, op_conf):
        symbol_id = self._NewSymbolId()
        self._InitOpConfSymbol(symbol_id, op_conf)
        return symbol_id

    def _NewSharedOpKernelObjectId4ParallelConfSymbolId(self, parallel_conf_sym):
        return self._NewObjectId(parallel_conf_sym)

    def _NewBlobObjectId(self, parallel_conf_sym):
        return self._NewObjectId(parallel_conf_sym)

    def _StatelessCall(self, device_tag, parallel_conf_sym,
                       job_conf_sym, op_conf_sym, shared_opkernel_obj,
                       input_triples, output_triples, mut2_output_triples):
        instruction = instr_util.InstructionProto()
        instruction.instr_type_name = "%s_StatelessCallOpKernel" % device_tag
        instruction.parallel_desc_symbol_id = parallel_conf_sym
        instruction.operand.append(_SymbolOperand(job_conf_sym))
        instruction.operand.append(_SymbolOperand(op_conf_sym))
        instruction.operand.append(_MutOperand(shared_opkernel_obj))
        instruction.operand.append(_OperandSeparator())
        for ibn_sym, index, lbn_object_id in input_triples:
            instruction.operand.append(_SymbolOperand(ibn_sym))
            instruction.operand.append(_Int64Operand(index))
            instruction.operand.append(_ConstOperand(lbn_object_id))
        instruction.operand.append(_OperandSeparator())
        for obn_sym, index, lbn_object_id in output_triples:
            instruction.operand.append(_SymbolOperand(obn_sym))
            instruction.operand.append(_Int64Operand(index))
            instruction.operand.append(_MutOperand(lbn_object_id))
        instruction.operand.append(_OperandSeparator())
        for obn_sym, index, lbn_object_id in mut2_output_triples:
            instruction.operand.append(_SymbolOperand(obn_sym))
            instruction.operand.append(_Int64Operand(index))
            instruction.operand.append(_Mut2Operand(lbn_object_id))
        self.instruction_list_.instruction.append(instruction)

    def _NewSymbolId(self):
        symbol_id = self.id_generator_.NewSymbolId()
        instruction = instr_util.InstructionProto()
        instruction.instr_type_name = "NewSymbol"
        instruction.operand.append(_Int64Operand(symbol_id))
        self.instruction_list_.instruction.append(instruction)
        return symbol_id

    def _NewObjectId(self, parallel_conf_sym):
        object_id = self.id_generator_.NewObjectId()
        instruction = instr_util.InstructionProto()
        instruction.instr_type_name = "NewObject"
        instruction.operand.append(_Int64Operand(parallel_conf_sym))
        instruction.operand.append(_Int64Operand(object_id))
        self.instruction_list_.instruction.append(instruction)
        return object_id

    def _InitStringSymbol(self, symbol_id, string):
        instruction = instr_util.InstructionProto()
        instruction.instr_type_name = "InitStringSymbol"
        instruction.operand.append(_InitSymbolOperand(symbol_id))
        self.instruction_list_.instruction.append(instruction)
        eager_symbol = eager_symbol_util.EagerSymbol()
        eager_symbol.symbol_id = symbol_id
        eager_symbol.string_symbol = string
        self.eager_symbol_list_.eager_symbol.append(eager_symbol)

    def _NewParallelConfSymbol(self, symbol_id, parallel_conf):
        instruction = instr_util.InstructionProto()
        instruction.instr_type_name = "NewParallelDescSymbol"
        instruction.operand.append(_Int64Operand(symbol_id))
        self.instruction_list_.instruction.append(instruction)
        eager_symbol = eager_symbol_util.EagerSymbol()
        eager_symbol.symbol_id = symbol_id
        eager_symbol.parallel_conf_symbol.CopyFrom(parallel_conf)
        self.eager_symbol_list_.eager_symbol.append(eager_symbol)

    def _InitJobConfSymbol(self, symbol_id, job_conf):
        instruction = instr_util.InstructionProto()
        instruction.instr_type_name = "InitJobDescSymbol"
        instruction.operand.append(_InitSymbolOperand(symbol_id))
        self.instruction_list_.instruction.append(instruction)
        eager_symbol = eager_symbol_util.EagerSymbol()
        eager_symbol.symbol_id = symbol_id
        eager_symbol.job_conf_symbol.CopyFrom(job_conf)
        self.eager_symbol_list_.eager_symbol.append(eager_symbol)

    def _InitOpConfSymbol(self, symbol_id, op_conf):
        instruction = instr_util.InstructionProto()
        instruction.instr_type_name = "InitOperatorConfSymbol"
        instruction.operand.append(_InitSymbolOperand(symbol_id))
        self.instruction_list_.instruction.append(instruction)
        eager_symbol = eager_symbol_util.EagerSymbol()
        eager_symbol.symbol_id = symbol_id
        eager_symbol.op_conf_symbol.CopyFrom(op_conf)
        self.eager_symbol_list_.eager_symbol.append(eager_symbol)

def _SymbolOperand(val):
    operand = instr_util.InstructionOperandProto()
    _SetSoleMirroredOperand(operand.symbol_operand, val)
    return operand

def _InitSymbolOperand(val):
    operand = instr_util.InstructionOperandProto()
    _SetSoleMirroredOperand(operand.init_symbol_operand, val)
    return operand

def _ConstOperand(val):
    operand = instr_util.InstructionOperandProto()
    _SetMirroredOperand(operand.const_operand, val)
    return operand

def _MutOperand(val):
    operand = instr_util.InstructionOperandProto()
    _SetMirroredOperand(operand.mut_operand, val)
    return operand

def _Mut2Operand(val):
    operand = instr_util.InstructionOperandProto()
    _SetMirroredOperand(operand.mut2_operand, val)
    return operand

def _Int64Operand(val):
    operand = instr_util.InstructionOperandProto()
    operand.int64_operand = val
    return operand

def _OperandSeparator():
    operand = instr_util.InstructionOperandProto()
    operand.separator.SetInParent()
    return operand

def _SetMirroredOperand(operand, val):
    operand.logical_object_id = val
    operand.current_global_device_id.SetInParent()

def _SetSoleMirroredOperand(operand, val):
    operand.logical_object_id = val
    operand.sole_mirrored_object.SetInParent()