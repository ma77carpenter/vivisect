import struct

import envi
import envi.memory as e_mem
import envi.registers as e_reg
import envi.memcanvas as e_memcanvas
import envi.memcanvas.renderers as e_rend
import envi.archs.h8 as e_h8
import vivisect
import platform
import unittest
from envi import IF_RET, IF_NOFALL, IF_BRANCH, IF_CALL, IF_COND
from envi.archs.h8.regs import *
from envi.archs.h8.const import *
from envi.archs.h8.parsers import *


# OPHEX, VA, repr, flags, emutests
instrs = [
        ( "8342", 0x4560, 'add.b #42, r3h', IF_B, () ),
        ( "7c6075f0", 0x4560, 'bixor #7, @er6', 0, () ),
        ( "7d507170", 0x4560, 'bnot #7, @er5', 0, () ),
        ( "0832", 0x4560, 'add.b r3h, r2h', IF_B, () ),
        ( "791d4745", 0x4560, 'add.w #4745, e5', IF_W, () ),
        ( "0932", 0x4560, 'add.w r3, r2', IF_W, () ),
        ( "7a1d00047145", 0x4560, 'add.l #47145, er5', IF_L, () ),
        ( "01406930", 0x4560, 'ldc.w @er3, ccr', IF_W, () ),
        ( "014069b0", 0x4560, 'stc.w ccr, @er3', IF_W, () ),
        ( "01c05023", 0x4560, 'mulxs.b r2h, r3', IF_B, () ),
        ( "01c05223", 0x4560, 'mulxs.w r2, er3', IF_W, () ),
        ( "01d05123", 0x4560, 'divxs.b r2h, r3', IF_B, () ),
        ( "01d05323", 0x4560, 'divxs.w r2, er3', IF_W, () ),
        ( "01f06423", 0x4560, 'or.l er2, er3', IF_L, () ),
        ( "01f06523", 0x4560, 'xor.l er2, er3', IF_L, () ),
        ( "01f06623", 0x4560, 'and.l er2, er3', IF_L, () ),
        ( "0a03", 0x4560, 'inc.b r3h', IF_B, () ),
        ( "0a83", 0x4560, 'add.l er0, er3', IF_L, () ),
        ( "0b83", 0x4560, 'adds #2, er3', 0, () ),
        ( "0b93", 0x4560, 'adds #4, er3', 0, () ),
        ( "0b53", 0x4560, 'inc.w #1, r3', IF_W, () ),
        ( "0bf3", 0x4560, 'inc.l #2, er3', IF_L, () ),
        ( "0f00", 0x4560, 'daa r0h', 0, () ),
        ( "0f93", 0x4560, 'mov.l er1, er3', IF_L, () ),
        ( "1a03", 0x4560, 'dec.b r3h', IF_B, () ),
        ( "1a83", 0x4560, 'sub.l er0, er3', IF_L, () ),
        ( "1b83", 0x4560, 'subs #2, er3', 0, () ),
        ( "1b93", 0x4560, 'subs #4, er3', 0, () ),
        ( "1b53", 0x4560, 'dec.w #1, r3', IF_W, () ),
        ( "1bf3", 0x4560, 'dec.l #2, er3', IF_L, () ),
        ( "1f00", 0x4560, 'das r0h', 0, () ),
        ( "5470", 0x4560, 'rts', IF_RET | IF_NOFALL, () ),
        ( "4670", 0x4560, 'bne 45d2:8', IF_BRANCH | IF_COND, () ),
        ( "4e90", 0x4560, 'bgt 44f2:8', IF_BRANCH | IF_COND, () ),
        ( "58500070", 0x4560, 'bcs 45d4:16', IF_BRANCH | IF_COND, () ),
        ( "58b0f070", 0x4560, 'bmi 35d4:16', IF_BRANCH | IF_COND, () ),
        ( "01006df2", 0x4560, 'push.l er2', IF_L, () ),
        ( "6dfa", 0x4560, 'push.w e2', IF_W, () ),
        ( "6df2", 0x4560, 'push.w r2', IF_W, () ),
        ( "6cda", 0x4560, 'mov.b r2l, @-er5', IF_B, () ),
        ( '01006df2', 0x4560, 'push.l er2', IF_L, () ),
        ( '6df2', 0x4560, 'push.w r2', IF_W, () ),
        ( '6de2', 0x4560, 'mov.w r2, @-er6', IF_W, () ),
        ( '6dda', 0x4560, 'mov.w e2, @-er5', IF_W, () ),
        ( '01006dd2', 0x4560, 'mov.l er2, @-er5', IF_L, () ),
        ( '6843', 0x4560, 'mov.b @er4, r3h', IF_B, () ),
        ( '68c3', 0x4560, 'mov.b r3h, @er4', IF_B, () ),
        ( '6ec34715', 0x4560, 'mov.b r3h, @(0x4715:16, er4)', IF_B, () ),
        ( '6ecb4715', 0x4560, 'mov.b r3l, @(0x4715:16, er4)', IF_B, () ),
        ( '01106d75', 0x4560, 'ldm.l @sp+, (er4-er5)', IF_L, () ),
        ( '01106df4', 0x4560, 'stm.l (er4-er5), @-sp', IF_L, () ),


        ( '8340', 0x0, 'add.b #40, r3h', IF_B, (
            {'setup':(('r3h',0xca),('CCR_C',0)), 'tests':(('r3h',0x0a),('CCR_C',1),('CCR_V',0)) }, ) ),
        ( '0832', 0x2, 'add.b r3h, r2h', IF_B, (
            {'setup':(('r3h',0xca),('r2h',0x40), ('CCR_C',0)), 'tests':(('r2h',0x0a),('CCR_C',1),('CCR_V',0)) }, ) ),
        ( '79134715', 0x4, 'add.w #4715, r3', IF_W, (
            {'setup':(('r3',0xccca),('CCR_C',0)), 'tests':(('r3',0x13df),('CCR_C',1),('CCR_V',0)) }, ) ),
        ( '0943', 0x8, 'add.w r4, r3', IF_W, (
            {'setup':(('r3',0xccca),('r4',0x4715), ('CCR_C',0)), 'tests':(('r3',0x13df),('CCR_C',1),('CCR_V',0)) }, ) ),
        ( '7A1300047145', 0xa, 'add.l #47145, er3', IF_L, () ),
        ( '0AA3', 0x10, 'add.l er2, er3', IF_L, () ),
        ( '0B03', 0x12, 'adds #1, er3', 0, () ),
        ( '0B83', 0x14, 'adds #2, er3', 0, () ),
        ( '0B93', 0x16, 'adds #4, er3', 0, () ),
        ( '9340', 0x18, 'addx #40, r3h', 0, () ),
        ( '0E43', 0x1a, 'addx r4h, r3h', 0, () ),
        ( 'E340', 0x1c, 'and.b #40, r3h', IF_B, () ),
        ( '1643', 0x1e, 'and.b r4h, r3h', IF_B, () ),
        ( '79634715', 0x20, 'and.w #4715, r3', IF_W, () ),
        ( '6643', 0x24, 'and.w r4, r3', IF_W, () ),
        ( '7A6300047145', 0x26, 'and.l #47145, er3', IF_L, () ),
        ( '01F06643', 0x2c, 'and.l er4, er3', IF_L, () ),
        ( '0640', 0x30, 'andc #40, ccr', 0, () ),
        ( '01410640', 0x32, 'andc #40, exr', 0, () ),
        ( '7643', 0x36, 'band #4, r3h', 0, () ),
        ( '7C307640', 0x38, 'band #4, @er3', 0, () ),
        ( '7E477640', 0x3c, 'band #4, @0xffff47:8', 0, () ),
        ( '6A1047157640', 0x40, 'band #4, @0x4715:16', 0, () ),
        ( '6A30000471457640', 0x46, 'band #4, @0x47145:32', 0, () ),
        ( '4040', 0x50, 'bra  0092:8', IF_BRANCH | IF_NOFALL, () ),
        ( '4140', 0x56, 'brn  0098:8', IF_BRANCH | IF_COND, () ),
        ( '4240', 0x5c, 'bhi  009e:8', IF_BRANCH | IF_COND, () ),
        ( '4340', 0x62, 'bls  00a4:8', IF_BRANCH | IF_COND, () ),
        ( '4440', 0x68, 'bcc  00aa:8', IF_BRANCH | IF_COND, () ),
        ( '4540', 0x6e, 'bcs  00b0:8', IF_BRANCH | IF_COND, () ),
        ( '4640', 0x74, 'bne  00b6:8', IF_BRANCH | IF_COND, () ),
        ( '4740', 0x7a, 'beq  00bc:8', IF_BRANCH | IF_COND, () ),
        ( '4840', 0x80, 'bvc  00c2:8', IF_BRANCH | IF_COND, () ),
        ( '4940', 0x86, 'bvs  00c8:8', IF_BRANCH | IF_COND, () ),
        ( '4a40', 0x8c, 'bpl  00ce:8', IF_BRANCH | IF_COND, () ),
        ( '4b40', 0x92, 'bmi  00d4:8', IF_BRANCH | IF_COND, () ),
        ( '4c40', 0x98, 'bge  00da:8', IF_BRANCH | IF_COND, () ),
        ( '4d40', 0x9e, 'blt  00e0:8', IF_BRANCH | IF_COND, () ),
        ( '4e40', 0xa4, 'bgt  00e6:8', IF_BRANCH | IF_COND, () ),
        ( '4f40', 0xaa, 'ble  00ec:8', IF_BRANCH | IF_COND, () ),
        ( '58004715', 0x50, 'bra  4768:16', IF_BRANCH | IF_NOFALL, () ),
        ( '58104715', 0x56, 'brn  476E:16', IF_BRANCH | IF_COND, () ),
        ( '58204715', 0x5c, 'bhi  4774:16', IF_BRANCH | IF_COND, () ),
        ( '58304715', 0x62, 'bls  477A:16', IF_BRANCH | IF_COND, () ),
        ( '58404715', 0x68, 'bcc  4780:16', IF_BRANCH | IF_COND, () ),
        ( '58504715', 0x6e, 'bcs  4786:16', IF_BRANCH | IF_COND, () ),
        ( '58604715', 0x74, 'bne  478C:16', IF_BRANCH | IF_COND, () ),
        ( '58704715', 0x7a, 'beq  4792:16', IF_BRANCH | IF_COND, () ),
        ( '58804715', 0x80, 'bvc  4798:16', IF_BRANCH | IF_COND, () ),
        ( '58904715', 0x86, 'bvs  479E:16', IF_BRANCH | IF_COND, () ),
        ( '58A04715', 0x8c, 'bpl  47A4:16', IF_BRANCH | IF_COND, () ),
        ( '58B04715', 0x92, 'bmi  47AA:16', IF_BRANCH | IF_COND, () ),
        ( '58C04715', 0x98, 'bge  47B0:16', IF_BRANCH | IF_COND, () ),
        ( '58D04715', 0x9e, 'blt  47B6:16', IF_BRANCH | IF_COND, () ),
        ( '58E04715', 0xa4, 'bgt  47BC:16', IF_BRANCH | IF_COND, () ),
        ( '58F04715', 0xaa, 'ble  47C2:16', IF_BRANCH | IF_COND, () ),
        ( '7243', 0xae, 'bclr #4, r3h', 0, () ),
        ( '7D307240', 0xb0, 'bclr #4, @er3', 0, () ),
        ( '7F407240', 0xb4, 'bclr #4, @0xffff40:8', 0, () ),
        ( '6A1847157240', 0xb8, 'bclr #4, @0x4715:16', 0, () ),
        ( '6A38000471457240', 0xbe, 'bclr #4, @0x47145:32', 0, () ),
        ( '6243', 0xc6, 'bclr r4h, r3h', 0, () ),
        ( '7D306240', 0xc8, 'bclr r4h, @er3', 0, () ),
        ( '7F406240', 0xcc, 'bclr r4h, @0xffff40:8', 0, () ),
        ( '6A1847156240', 0xd0, 'bclr r4h, @0x4715:16', 0, () ),
        ( '6A38000471456240', 0xd6, 'bclr r4h, @0x47145:32', 0, () ),
        ( '76C3', 0xde, 'biand #4, r3h', 0, () ),
        ( '7C3076C0', 0xe0, 'biand #4, @er3', 0, () ),
        ( '7E4076C0', 0xe4, 'biand #4, @0xffff40:8', 0, () ),
        ( '6A10471576C0', 0xe8, 'biand #4, @0x4715:16', 0, () ),
        ( '6A300004714576C0', 0xee, 'biand #4, @0x47145:32', 0, () ),
        ( '77C3', 0xf6, 'bild #4, r3h', 0, () ),
        ( '7C3077C0', 0xf8, 'bild #4, @er3', 0, () ),
        ( '7E4077C0', 0xfc, 'bild #4, @0xffff40:8', 0, () ),
        ( '6A10471577C0', 0x100, 'bild #4, @0x4715:16', 0, () ),
        ( '6A300004714577C0', 0x106, 'bild #4, @0x47145:32', 0, () ),
        ( '74C3', 0x10e, 'bior #4, r3h', 0, () ),
        ( '7C3074C0', 0x110, 'bior #4, @er3', 0, () ),
        ( '7E4074C0', 0x114, 'bior #4, @0xffff40:8', 0, () ),
        ( '6A10471574C0', 0x118, 'bior #4, @0x4715:16', 0, () ),
        ( '6A300004714574C0', 0x11e, 'bior #4, @0x47145:32', 0, () ),
        ( '7D3067C0', 0x126, 'bist #4, @er3', 0, () ),
        ( '7F4067C0', 0x12a, 'bist #4, @0xffff40:8', 0, () ),
        ( '6A18471567C0', 0x12e, 'bist #4, @0x4715:16', 0, () ),
        ( '6A380004714567C0', 0x134, 'bist #4, @0x47145:32', 0, () ),
        ( '75C3', 0x13c, 'bixor #4, r3h', 0, () ),
        ( '7C3075C0', 0x13e, 'bixor #4, @er3', 0, () ),
        ( '7E4075C0', 0x142, 'bixor #4, @0xffff40:8', 0, () ),
        ( '6A10471575C0', 0x146, 'bixor #4, @0x4715:16', 0, () ),
        ( '6A300004714575C0', 0x14c, 'bixor #4, @0x47145:32', 0, () ),
        ( '7743', 0x154, 'bld  #4, r3h', 0, () ),
        ( '7C307740', 0x156, 'bld  #4, @er3', 0, () ),
        ( '7E407740', 0x15a, 'bld  #4, @0xffff40:8', 0, () ),
        ( '6A1047157740', 0x15e, 'bld  #4, @0x4715:16', 0, () ),
        ( '6A30000471457740', 0x164, 'bld  #4, @0x47145:32', 0, () ),
        ( '7143', 0x16c, 'bnot #4, r3h', 0, () ),
        ( '7D307140', 0x16e, 'bnot #4, @er3', 0, () ),
        ( '7F407140', 0x172, 'bnot #4, @0xffff40:8', 0, () ),
        ( '6A1847157140', 0x176, 'bnot #4, @0x4715:16', 0, () ),
        ( '6A38000471457140', 0x17c, 'bnot #4, @0x47145:32', 0, () ),
        ( '6143', 0x184, 'bnot r4h, r3h', 0, () ),
        ( '7D306140', 0x186, 'bnot r4h, @er3', 0, () ),
        ( '7F406140', 0x18a, 'bnot r4h, @0xffff40:8', 0, () ),
        ( '6A1847156140', 0x18e, 'bnot r4h, @0x4715:16', 0, () ),
        ( '6A38000471456140', 0x194, 'bnot r4h, @0x47145:32', 0, () ),
        ( '7443', 0x19c, 'bor  #4, r3h', 0, () ),
        ( '7C307440', 0x19e, 'bor  #4, @er3', 0, () ),
        ( '7E407440', 0x1a2, 'bor  #4, @0xffff40:8', 0, () ),
        ( '6A1047157440', 0x1a6, 'bor  #4, @0x4715:16', 0, () ),
        ( '6A30000471457440', 0x1ac, 'bor  #4, @0x47145:32', 0, () ),
        ( '7043', 0x1b4, 'bset #4, r3h', 0, () ),
        ( '7D307040', 0x1b6, 'bset #4, @er3', 0, () ),
        ( '7F407040', 0x1ba, 'bset #4, @0xffff40:8', 0, () ),
        ( '6A1847157040', 0x1be, 'bset #4, @0x4715:16', 0, () ),
        ( '6A38000471457040', 0x1c4, 'bset #4, @0x47145:32', 0, () ),
        ( '6043', 0x1cc, 'bset r4h, r3h', 0, () ),
        ( '7D306040', 0x1ce, 'bset r4h, @er3', 0, () ),
        ( '7F406040', 0x1d2, 'bset r4h, @0xffff40:8', 0, () ),
        ( '6A1847156040', 0x1d6, 'bset r4h, @0x4715:16', 0, () ),
        ( '6A38000471456040', 0x1dc, 'bset r4h, @0x47145:32', 0, () ),
        ( '5C004242', 0x1e6, 'bsr  442C:16', IF_CALL, () ),
        ( '6743', 0x1ea, 'bst  #4, r3h', 0, () ),
        ( '7D306740', 0x1ec, 'bst  #4, @er3', 0, () ),
        ( '7F406740', 0x1f0, 'bst  #4, @0xffff40:8', 0, () ),
        ( '6A1847156740', 0x1f4, 'bst  #4, @0x4715:16', 0, () ),
        ( '6A38000471456740', 0x1fa, 'bst  #4, @0x47145:32', 0, () ),
        ( '7343', 0x202, 'btst #4, r3h', 0, () ),
        ( '7C307340', 0x204, 'btst #4, @er3', 0, () ),
        ( '7E407340', 0x208, 'btst #4, @0xffff40:8', 0, () ),
        ( '6A1047157340', 0x20c, 'btst #4, @0x4715:16', 0, () ),
        ( '6A30000471457340', 0x212, 'btst #4, @0x47145:32', 0, () ),
        ( '6343', 0x21a, 'btst r4h, r3h', 0, () ),
        ( '7C306340', 0x21c, 'btst r4h, @er3', 0, () ),
        ( '7E406340', 0x220, 'btst r4h, @0xffff40:8', 0, () ),
        ( '6A1047156340', 0x224, 'btst r4h, @0x4715:16', 0, () ),
        ( '6A30000471456340', 0x22a, 'btst r4h, @0x47145:32', 0, () ),
        ( '7543', 0x232, 'bxor #4, r3h', 0, () ),
        ( '7C307540', 0x234, 'bxor #4, @er3', 0, () ),
        ( '7E407540', 0x238, 'bxor #4, @0xffff40:8', 0, () ),
        ( '6A1047157540', 0x23c, 'bxor #4, @0x4715:16', 0, () ),
        ( '6A30000471457540', 0x242, 'bxor #4, @0x47145:32', 0, () ),
        ( 'A340', 0x24a, 'cmp.b #40, r3h', IF_B, () ),
        ( '1C43', 0x24c, 'cmp.b r4h, r3h', IF_B, () ),
        ( '79234715', 0x24e, 'cmp.w #4715, r3', IF_W, () ),
        ( '1D43', 0x252, 'cmp.w r4, r3', IF_W, () ),
        ( '7A2300047145', 0x254, 'cmp.l #47145, er3', IF_L, () ),
        ( '1FC3', 0x25a, 'cmp.l er4, er3', IF_L, () ),
        ( '0F03', 0x25c, 'daa  r3h', 0, () ),
        ( '1F03', 0x25e, 'das  r3h', 0, () ),
        ( '1A03', 0x260, 'dec.b r3h', IF_B, () ),
        ( '1B53', 0x262, 'dec.w #1, r3', IF_W, () ),
        ( '1BD3', 0x264, 'dec.w #2, r3', IF_W, () ),
        ( '1B73', 0x266, 'dec.l #1, er3', IF_L, () ),
        ( '1BF3', 0x268, 'dec.l #2, er3', IF_L, () ),
        ( '01D05143', 0x26a, 'divxs.b r4h, r3', IF_B, () ),
        ( '01D05343', 0x26e, 'divxs.w r4, er3', IF_W, () ),
        ( '5143', 0x272, 'divxu.b r4h, r3', IF_B, () ),
        ( '5343', 0x274, 'divxu.w r4, er3', IF_W, () ),
        ( '7B5C598F', 0x276, 'eepmov.b', IF_B, () ),
        #( '7BD4598F', 0x27a, 'eepmov.w', IF_W, () ),
        ( '17D3', 0x27e, 'exts.w r3', IF_W, () ),
        ( '17F3', 0x280, 'exts.l er3', IF_L, () ),
        ( '1753', 0x282, 'extu.w r3', IF_W, () ),
        ( '1773', 0x284, 'extu.l er3', IF_L, () ),
        ( '0A03', 0x286, 'inc.b r3h', IF_B, () ),
        ( '0B53', 0x288, 'inc.w #1, r3', IF_W, () ),
        ( '0BD3', 0x28a, 'inc.w #2, r3', IF_W, () ),
        ( '0B73', 0x28c, 'inc.l #1, er3', IF_L, () ),
        ( '0BF3', 0x28e, 'inc.l #2, er3', IF_L, () ),
        ( '5940', 0x290, 'jmp  @er4', IF_BRANCH | IF_NOFALL, () ),
        ( '5A047145', 0x292, 'jmp  @0x47145:24', IF_BRANCH | IF_NOFALL, () ),
        ( '5D40', 0x298, 'jsr  @er4', IF_CALL, () ),
        ( '5E047145', 0x29a, 'jsr  @0x47145:24', IF_CALL, () ),
        ( '0740', 0x2a0, 'ldc.b #40, ccr', IF_B, () ),
        ( '01410740', 0x2a2, 'ldc.b #40, exr', IF_B, () ),
        ( '0304', 0x2a6, 'ldc.b r4h, ccr', IF_B, () ),
        ( '0314', 0x2a8, 'ldc.b r4h, exr', IF_B, () ),
        ( '01406940', 0x2aa, 'ldc.w @er4, ccr', IF_W, () ),
        ( '01416940', 0x2ae, 'ldc.w @er4, exr', IF_W, () ),
        ( '01406F404715', 0x2b2, 'ldc.w @(0x4715:16,er4), ccr', IF_W, () ),
        ( '01416F404715', 0x2b8, 'ldc.w @(0x4715:16,er4), exr', IF_W, () ),
        ( '014078406B2000047145', 0x2be, 'ldc.w @(0x47145:32,er4), ccr', IF_W, () ),
        ( '014178406B2000047145', 0x2c8, 'ldc.w @(0x47145:32,er4), exr', IF_W, () ),
        ( '01406D40', 0x2d2, 'ldc.w @er4+, ccr', IF_W, () ),
        ( '01416D40', 0x2d6, 'ldc.w @er4+, exr', IF_W, () ),
        ( '01406B004715', 0x2da, 'ldc.w @0x4715:16, ccr', IF_W, () ),
        ( '01416B004715', 0x2e0, 'ldc.w @0x4715:16, exr', IF_W, () ),
        ( '01406B2000047145', 0x2e6, 'ldc.w @0x47145:32, ccr', IF_W, () ),
        ( '01416B2000047145', 0x2ee, 'ldc.w @0x47145:32, exr', IF_W, () ),
        ( 'F340', 0x302, 'mov.b #40, r3h', IF_B, () ),
        ( '0C43', 0x304, 'mov.b r4h, r3h', IF_B, () ),
        ( '6843', 0x306, 'mov.b @er4, r3h', IF_B, () ),
        ( '6E434715', 0x308, 'mov.b @(0x4715:16,er4), r3h', IF_B, () ),
        ( '78406A2300047145', 0x30c, 'mov.b @(0x47145:32,er4), r3h', IF_B, () ),
        ( '6C43', 0x314, 'mov.b @er4+, r3h', IF_B, () ),
        ( '2340', 0x316, 'mov.b @0xffff40:8, r3h', IF_B, () ),
        ( '6A034715', 0x318, 'mov.b @0x4715:16, r3h', IF_B, () ),
        ( '78306A2300047145', 0x31c, 'mov.b @(0x47145:32,er3), r3h', IF_B, () ),
        ( '6CB4', 0x324, 'mov.b r4h, @-er3', IF_B, () ),
        ( '3440', 0x326, 'mov.b r4h, @0xffff40:8', IF_B, () ),
        ( '6A844715', 0x328, 'mov.b r4h, @0x4715:16', IF_B, () ),
        ( '6AA400047145', 0x32c, 'mov.b r4h, @0x47145:32', IF_B, () ),
        ( '79044715', 0x332, 'mov.w #4715, r4', IF_W, () ),
        ( '0D43', 0x336, 'mov.w r4, r3', IF_W, () ),
        ( '6943', 0x338, 'mov.w @er4, r3', IF_W, () ),
        ( '6F434715', 0x33a, 'mov.w @(0x4715:16,er4), r3', IF_W, () ),
        ( '78406B2300047145', 0x33e, 'mov.w @(0x47145:32,er4), r3', IF_W, () ),
        ( '6D43', 0x346, 'mov.w @er4+, r3', IF_W, () ),
        ( '6B034715', 0x348, 'mov.w @0x4715:16, r3', IF_W, () ),
        ( '6B2300047145', 0x34c, 'mov.w @0x47145:32, r3', IF_W, () ),
        ( '69B4', 0x352, 'mov.w r4, @er3', IF_W, () ),
        ( '6FB44715', 0x354, 'mov.w r4, @(0x4715:16,er3)', IF_W, () ),
        ( '78306BA400047145', 0x358, 'mov.w r4, @(0x47145:32,er3)', IF_W, () ),
        ( '6DB4', 0x360, 'mov.w r4, @-er3', IF_W, () ),
        ( '6B844715', 0x362, 'mov.w r4, @0x4715:16', IF_W, () ),
        ( '6BA400047145', 0x366, 'mov.w r4, @0x47145:32', IF_W, () ),
        ( '7A0300047145', 0x36c, 'mov.l #47145, er3', IF_L, () ),
        ( '0FC3', 0x372, 'mov.l er4, er3', IF_L, () ),
        ( '01006943', 0x374, 'mov.l @er4, er3', IF_L, () ),
        ( '01006F434715', 0x378, 'mov.l @(0x4715:16,er4), er3', IF_L, () ),
        ( '010078406B2300047145', 0x37e, 'mov.l @(0x47145:32,er4), er3', IF_L, () ),
        ( '01006D43', 0x388, 'mov.l @er4+, er3', IF_L, () ),
        ( '01006B034715', 0x38c, 'mov.l @0x4715:16, er3', IF_L, () ),
        ( '01006B2300047145', 0x392, 'mov.l @0x47145:32, er3', IF_L, () ),
        ( '010069B4', 0x39a, 'mov.l er4, @er3', IF_L, () ),
        ( '01006FB44715', 0x39e, 'mov.l er4, @(0x4715:16,er3)', IF_L, () ),
        ( '010078306BA400047145', 0x3a4, 'mov.l er4, @(0x47145:32,er3)', IF_L, () ),
        ( '01006DB4', 0x3ae, 'mov.l er4, @-er3', IF_L, () ),
        ( '01006B844715', 0x3b2, 'mov.l er4, @0x4715:16', IF_L, () ),
        ( '01006BA400047145', 0x3b8, 'mov.l er4, @0x47145:32', IF_L, () ),
        ( '01C05043', 0x3c0, 'mulxs.b r4h, r3', IF_B, () ),
        ( '01C05243', 0x3c4, 'mulxs.w r4, er3', IF_W, () ),
        ( '5043', 0x3c8, 'mulxu.b r4h, r3', IF_B, () ),
        ( '5243', 0x3ca, 'mulxu.w r4, er3', IF_W, () ),
        ( '1783', 0x3cc, 'neg.b r3h', IF_B, () ),
        ( '1793', 0x3ce, 'neg.w r3', IF_W, () ),
        ( '17B3', 0x3d0, 'neg.l er3', IF_L, () ),
        ( '0000', 0x3d2, 'nop', 0, () ),
        ( '1703', 0x3d4, 'not.b r3h', IF_B, () ),
        ( '1713', 0x3d6, 'not.w r3', IF_W, () ),
        ( '1733', 0x3d8, 'not.l er3', IF_L, () ),
        ( 'C340', 0x3da, 'or.b #40, r3h', IF_B, () ),
        ( '1443', 0x3dc, 'or.b r4h, r3h', IF_B, () ),
        ( '79434715', 0x3de, 'or.w #4715, r3', IF_W, () ),
        ( '6443', 0x3e2, 'or.w r4, r3', IF_W, () ),
        ( '7A4300047145', 0x3e4, 'or.l #47145, er3', IF_L, () ),
        ( '01F06443', 0x3ea, 'or.l er4, er3', IF_L, () ),
        ( '0440', 0x3ee, 'orc  #40, ccr', 0, () ),
        ( '01410440', 0x3f0, 'orc  #40, exr', 0, () ),
        ( '6D74', 0x3f4, 'pop.w r4', IF_W, () ),
        ( '01006D74', 0x3f6, 'pop.l er4', IF_L, () ),
        ( '6DF4', 0x3fa, 'push.w r4', IF_W, () ),
        ( '01006DF4', 0x3fc, 'push.l er4', IF_L, () ),
        ( '1283', 0x400, 'rotl.b r3h', IF_B, (
            {'setup':(('r3h',0xaa),('CCR_C',0)), 'tests':(('r3h',0x55),('CCR_C',1),('CCR_V',0)) }, ) ),
        ( '12C3', 0x402, 'rotl.b #2, r3h', IF_B, (
            {'setup':(('r3h',0xaa),('CCR_C',0)), 'tests':(('r3h',0xaa),('CCR_C',0),('CCR_V',0)) },
            {'setup':(('r3h',0x7a),('CCR_C',0)), 'tests':(('r3h',0xe9),('CCR_C',1),('CCR_V',0)) },
            ) ),
        ( '1293', 0x404, 'rotl.w r3', IF_W, (
            {'setup':(('r3',0xabcd),('CCR_C',0)), 'tests':(('r3',0x579b),('CCR_C',1),('CCR_V',0)) }, ) ),
        ( '12D3', 0x406, 'rotl.w #2, r3', IF_W, (
            {'setup':(('r3',0xabcd),('CCR_C',0)), 'tests':(('r3',0xaf36),('CCR_C',0),('CCR_V',0)) }, ) ),
        ( '12B3', 0x408, 'rotl.l er3', IF_L, (
            {'setup':(('er3',0xbadfaaaa),('CCR_C',0)), 'tests':(('er3',0x75bf5555),('CCR_C',1),('CCR_V',0))},
            {'setup':(('er3',0x7adfaaaa),('CCR_C',0)), 'tests':(('er3',0xf5bf5554),('CCR_C',0),('CCR_V',0))},
            )),
        ( '12F3', 0x40a, 'rotl.l #2, er3', IF_L, (
            {'setup':(('er3',0xabcdef12),('CCR_C',0)), 'tests':(('er3',0xaf37bc4a),('CCR_C',0),('CCR_V',0))},
            {'setup':(('er3',0x6bcdef12),('CCR_C',0)), 'tests':(('er3',0xaf37bc49),('CCR_C',1),('CCR_V',0))},
            )),
        ( '1383', 0x40c, 'rotr.b r3h', IF_B, (
            {'setup':(('r3h',0xaa),('CCR_C',0)), 'tests':(('r3h',0x55),('CCR_C',0),('CCR_V',0)) },
            {'setup':(('r3h',0xab),('CCR_C',0)), 'tests':(('r3h',0xd5),('CCR_C',1),('CCR_V',0)) },
            ) ),
        ( '13C3', 0x40e, 'rotr.b #2, r3h', IF_B, (
            {'setup':(('r3h',0xaa),('CCR_C',0)), 'tests':(('r3h',0xaa),('CCR_C',1),('CCR_V',0)) }, 
            {'setup':(('r3h',0xab),('CCR_C',0)), 'tests':(('r3h',0xea),('CCR_C',1),('CCR_V',0)) },
            ) ),
        ( '1393', 0x410, 'rotr.w r3', IF_W, (
            {'setup':(('r3',0xccaa),('CCR_C',0)), 'tests':(('r3',0x6655),('CCR_C',0),('CCR_V',0)) }, ) ),
        ( '13D3', 0x412, 'rotr.w #2, r3', IF_W, (
            {'setup':(('r3',0xccaa),('CCR_C',0)), 'tests':(('r3',0xb32a),('CCR_C',1),('CCR_V',0)) }, ) ),
        ( '13B3', 0x414, 'rotr.l er3', IF_L, (
            {'setup':(('er3',0xabcdefaa),('CCR_C',0)), 'tests':(('er3',0x55e6f7d5),('CCR_C',0),('CCR_V',0))},
            {'setup':(('er3',0x7bcdefaa),('CCR_C',0)), 'tests':(('er3',0x3de6f7d5),('CCR_C',0),('CCR_V',0))},
            ) ),
        ( '13F3', 0x416, 'rotr.l #2, er3', IF_L, (
            {'setup':(('er3',0xabcdefaa),('CCR_C',0)), 'tests':(('er3',0xaaf37bea),('CCR_C',1),('CCR_V',0))},
            {'setup':(('er3',0x7bcdefaa),('CCR_C',0)), 'tests':(('er3',0x9ef37bea),('CCR_C',1),('CCR_V',0))},
            )),
        ( '1203', 0x418, 'rotxl.b r3h', IF_B, (
            {'setup':(('r3h',0xaa),('CCR_C',0)), 'tests':(('r3h',0x54),('CCR_C',1),('CCR_V',0)) },
            {'setup':(('r3h',0xaa),('CCR_C',1)), 'tests':(('r3h',0x55),('CCR_C',1),('CCR_V',0)) },
            ) ),
        ( '1243', 0x41a, 'rotxl.b #2, r3h', IF_B, (
            {'setup':(('r3h',0xaa),('CCR_C',1)), 'tests':(('r3h',0xab),('CCR_C',0),('CCR_V',0)) },
            {'setup':(('r3h',0x7a),('CCR_C',0)), 'tests':(('r3h',0xe8),('CCR_C',1),('CCR_V',0)) },
            ) ),
        ( '1213', 0x41c, 'rotxl.w r3', IF_W, (
            {'setup':(('r3',0xabcd),('CCR_C',0)), 'tests':(('r3',0x579a),('CCR_C',1),('CCR_V',0)) },
            {'setup':(('r3',0xabcd),('CCR_C',1)), 'tests':(('r3',0x579b),('CCR_C',1),('CCR_V',0)) },
            ) ),
        ( '1253', 0x41e, 'rotxl.w #2, r3', IF_W, (
            {'setup':(('r3',0xabcd),('CCR_C',0)), 'tests':(('r3',0xaf35),('CCR_C',0),('CCR_V',0)) },
            {'setup':(('r3',0xabcd),('CCR_C',1)), 'tests':(('r3',0xaf37),('CCR_C',0),('CCR_V',0)) },
            ) ),
        ( '1233', 0x420, 'rotxl.l er3', IF_L, (
            {'setup':(('er3',0xbadfaaaa),('CCR_C',1)), 'tests':(('er3',0x75bf5555),('CCR_C',1),('CCR_V',0))},
            {'setup':(('er3',0x7adfaaaa),('CCR_C',0)), 'tests':(('er3',0xf5bf5554),('CCR_C',0),('CCR_V',0))},
            ) ),
        ( '1273', 0x422, 'rotxl.l #2, er3', IF_L, (
            {'setup':(('er3',0xabcdef12),('CCR_C',0)), 'tests':(('er3',0xaf37bc49),('CCR_C',0),('CCR_V',0))},
            {'setup':(('er3',0x6bcdef12),('CCR_C',1)), 'tests':(('er3',0xaf37bc4a),('CCR_C',1),('CCR_V',0))},
            ) ),
        ( '1303', 0x424, 'rotxr.b r3h', IF_B, (
            {'setup':(('r3h',0xaa),('CCR_C',1)), 'tests':(('r3h',0xd5),('CCR_C',0),('CCR_V',0)) },
            {'setup':(('r3h',0xab),('CCR_C',0)), 'tests':(('r3h',0x55),('CCR_C',1),('CCR_V',0)) },
            ) ),
        ( '1343', 0x426, 'rotxr.b #2, r3h', IF_B, (
            {'setup':(('r3h',0xaa),('CCR_C',1)), 'tests':(('r3h',0x6a),('CCR_C',1),('CCR_V',0)) }, 
            {'setup':(('r3h',0xab),('CCR_C',0)), 'tests':(('r3h',0xaa),('CCR_C',1),('CCR_V',0)) },
            ) ),
        ( '1313', 0x428, 'rotxr.w r3', IF_W, (
            {'setup':(('r3',0xccaa),('CCR_C',0)), 'tests':(('r3',0x6655),('CCR_C',0),('CCR_V',0)) }, ) ),
        ( '1353', 0x42a, 'rotxr.w #2, r3', IF_W, (
            {'setup':(('r3',0xccaa),('CCR_C',1)), 'tests':(('r3',0x732a),('CCR_C',1),('CCR_V',0)) }, ) ),
        ( '1333', 0x42c, 'rotxr.l er3', IF_L, (
            {'setup':(('er3',0xabcdefaa),('CCR_C',0)), 'tests':(('er3',0x55e6f7d5),('CCR_C',0),('CCR_V',0))},
            {'setup':(('er3',0x7bcdefaa),('CCR_C',1)), 'tests':(('er3',0xbde6f7d5),('CCR_C',0),('CCR_V',0))},
            ) ),
        ( '1373', 0x42e, 'rotxr.l #2, er3', IF_L, (
            {'setup':(('er3',0xabcdefaa),('CCR_C',0)), 'tests':(('er3',0x2af37bea),('CCR_C',1),('CCR_V',0))},
            {'setup':(('er3',0x7bcdefaa),('CCR_C',1)), 'tests':(('er3',0x5ef37bea),('CCR_C',1),('CCR_V',0))},
            ) ),
        ( '5670', 0x430, 'rte', IF_RET | IF_NOFALL, () ),
        ( '5470', 0x432, 'rts', IF_RET | IF_NOFALL, () ),
        ( '1083', 0x434, 'shal.b r3h', IF_B,     (
            {'setup':(('r3h',0xaa),('CCR_C',0)), 'tests':(('r3h',0x54),('CCR_C',1),('CCR_V',1)) }, ) ),
        ( '10C3', 0x436, 'shal.b #2, r3h', IF_B, (
            {'setup':(('r3h',0xaa),('CCR_C',0)), 'tests':(('r3h',0xa8),('CCR_C',0),('CCR_V',1)) },
            {'setup':(('r3h',0x7a),('CCR_C',0)), 'tests':(('r3h',0xe8),('CCR_C',1),('CCR_V',1)) },
            )),
        ( '1093', 0x438, 'shal.w r3', IF_W,      (
            {'setup':(('r3',0xabcd),('CCR_C',0)), 'tests':(('r3',0x579a),('CCR_C',1),('CCR_V',1)) }, ) ),
        ( '10D3', 0x43a, 'shal.w #2, r3', IF_W,  (
            {'setup':(('r3',0xabcd),('CCR_C',0)), 'tests':(('r3',0xaf34),('CCR_C',0),('CCR_V',1)) }, ) ),
        ( '10B3', 0x43c, 'shal.l er3', IF_L,     (
            {'setup':(('er3',0xbadfaaaa),('CCR_C',0)), 'tests':(('er3',0x75bf5554),('CCR_C',1),('CCR_V',1))},)),
        ( '10F3', 0x43e, 'shal.l #2, er3', IF_L, (
            {'setup':(('er3',0xabcdef12),('CCR_C',0)), 'tests':(('er3',0xaf37bc48),('CCR_C',0),('CCR_V',1))},)),
        ( '1183', 0x440, 'shar.b r3h', IF_B,     (
            {'setup':(('r3h',0xaa),('CCR_C',0)), 'tests':(('r3h',0xd5),('CCR_C',0),('CCR_V',0)) },
            {'setup':(('r3h',0x3a),('CCR_C',0)), 'tests':(('r3h',0x1d),('CCR_C',0),('CCR_V',0)) },
            )),
        ( '11C3', 0x442, 'shar.b #2, r3h', IF_B, (
            {'setup':(('r3h',0xaa),('CCR_C',0)), 'tests':(('r3h',0xea),('CCR_C',1),('CCR_V',0)) }, 
            {'setup':(('r3h',0xab),('CCR_C',0)), 'tests':(('r3h',0xea),('CCR_C',1),('CCR_V',0)) },
            )),
        ( '1193', 0x444, 'shar.w r3', IF_W,      (
            {'setup':(('r3',0xccaa),('CCR_C',0)), 'tests':(('r3',0xe655),('CCR_C',0),('CCR_V',0)) }, ) ),
        ( '11D3', 0x446, 'shar.w #2, r3', IF_W,  (
            {'setup':(('r3',0xccaa),('CCR_C',0)), 'tests':(('r3',0xf32a),('CCR_C',1),('CCR_V',0)) }, ) ),
        ( '11B3', 0x448, 'shar.l er3', IF_L,     (
            {'setup':(('er3',0xabcdefaa),('CCR_C',0)), 'tests':(('er3',0xd5e6f7d5),('CCR_C',0),('CCR_V',0))},
            {'setup':(('er3',0x7bcdefaa),('CCR_C',0)), 'tests':(('er3',0x3de6f7d5),('CCR_C',0),('CCR_V',0))},
            )),

        ( '11F3', 0x44a, 'shar.l #2, er3', IF_L, (
            {'setup':(('er3',0xabcdefaa),('CCR_C',0)), 'tests':(('er3',0xeaf37bea),('CCR_C',1),('CCR_V',0))},)),
        ( '1003', 0x44c, 'shll.b r3h', IF_B,     (
            {'setup':(('r3h',0xaa),('CCR_C',0)), 'tests':(('r3h',0x54),('CCR_C',1),('CCR_V',0)) }, ) ),
        ( '1043', 0x44e, 'shll.b #2, r3h', IF_B, (
            {'setup':(('r3h',0xaa),('CCR_C',0)), 'tests':(('r3h',0xa8),('CCR_C',0),('CCR_V',0)) }, ) ),
        ( '1013', 0x450, 'shll.w r3', IF_W,      (
            {'setup':(('r3',0xaacc),('CCR_C',0)), 'tests':(('r3',0x5598),('CCR_C',1),('CCR_V',0)) }, ) ),
        ( '1053', 0x452, 'shll.w #2, r3', IF_W,  (
            {'setup':(('r3',0xaacc),('CCR_C',0)), 'tests':(('r3',0xab30),('CCR_C',0),('CCR_V',0)) }, ) ),
        ( '1033', 0x454, 'shll.l er3', IF_L,     (
            {'setup':(('er3',0xabcdefaa),('CCR_C',0)), 'tests':(('er3',0x579bdf54),('CCR_C',1),('CCR_V',0))},)),
        ( '1073', 0x456, 'shll.l #2, er3', IF_L, (
            {'setup':(('er3',0xabcdefaa),('CCR_C',0)), 'tests':(('er3',0xaf37bea8),('CCR_C',0),('CCR_V',0))},)),
        ( '1103', 0x458, 'shlr.b r3h', IF_B,     (
            {'setup':(('r3h',0xaa),('CCR_C',0)), 'tests':(('r3h',0x55),('CCR_C',0),('CCR_V',0)) }, ) ),
        ( '1143', 0x45a, 'shlr.b #2, r3h', IF_B, (
            {'setup':(('r3h',0xaa),('CCR_C',0)), 'tests':(('r3h',0x2a),('CCR_C',1),('CCR_V',0)) }, ) ),
        ( '1113', 0x45c, 'shlr.w r3', IF_W,      (
            {'setup':(('r3',0xacca),('CCR_C',0)), 'tests':(('r3',0x5665),('CCR_C',0),('CCR_V',0)) }, ) ),
        ( '1153', 0x45e, 'shlr.w #2, r3', IF_W,  (
            {'setup':(('r3',0xacca),('CCR_C',0)), 'tests':(('r3',0x2b32),('CCR_C',1),('CCR_V',0)) }, ) ),
        ( '1133', 0x460, 'shlr.l er3', IF_L,     (
            {'setup':(('er3',0xabcdefaa),('CCR_C',0)), 'tests':(('er3',0x55e6f7d5),('CCR_C',0),('CCR_V',0))},)),
        ( '1173', 0x462, 'shlr.l #2, er3', IF_L, (
            {'setup':(('er3',0xabcdefaa),('CCR_C',0)), 'tests':(('er3',0x2af37bea),('CCR_C',1),('CCR_V',0))},)),
        ( '0180', 0x464, 'sleep', 0, () ),
        ( '0203', 0x466, 'stc.b ccr, r3h', IF_B, () ),
        ( '0213', 0x468, 'stc.b exr, r3h', IF_B, () ),
        ( '014069B0', 0x46a, 'stc.w ccr, @er3', IF_W, () ),
        ( '014169B0', 0x46e, 'stc.w exr, @er3', IF_W, () ),
        ( '01406FB04715', 0x472, 'stc.w ccr, @(0x4715:16,er3)', IF_W, () ),
        ( '01416FB04715', 0x478, 'stc.w exr, @(0x4715:16,er3)', IF_W, () ),
        ( '014078306BA000047145', 0x47e, 'stc.w ccr, @(0x47145:32,er3)', IF_W, () ),
        ( '014178306BA000047145', 0x488, 'stc.w exr, @(0x47145:32,er3)', IF_W, () ),
        ( '01406D30', 0x492, 'ldc.w @er3+, ccr', IF_W, () ),
        ( '01416D30', 0x496, 'ldc.w @er3+, exr', IF_W, () ),
        ( '01406B804715', 0x49a, 'stc.w ccr, @0x4715:16', IF_W, () ),
        ( '01416B804715', 0x4a0, 'stc.w exr, @0x4715:16', IF_W, () ),
        ( '01406BA000047145', 0x4a6, 'stc.w ccr, @0x47145:32', IF_W, () ),
        ( '01416BA000047145', 0x4ae, 'stc.w exr, @0x47145:32', IF_W, () ),
        ( '1843', 0x4c2, 'sub.b r4h, r3h', IF_B, () ),
        ( '79334715', 0x4c4, 'sub.w #4715, r3', IF_W, () ),
        ( '1943', 0x4c8, 'sub.w r4, r3', IF_W, () ),
        ( '7A3300047145', 0x4ca, 'sub.l #47145, er3', IF_L, () ),
        ( '1AC3', 0x4d0, 'sub.l er4, er3', IF_L, () ),
        ( '1B03', 0x4d2, 'subs #1, er3', 0, () ),
        ( '1B83', 0x4d4, 'subs #2, er3', 0, () ),
        ( '1B93', 0x4d6, 'subs #4, er3', 0, () ),
        ( 'B340', 0x4d8, 'subx #40, r3h', 0, () ),
        ( '1E43', 0x4da, 'subx r4h, r3h', 0, () ),
        ( '01E07B3C', 0x4dc, 'tas  @er3', 0, () ),
        ( '5730', 0x4e0, 'trapa #3', IF_NOFALL, () ),
        ( 'D340', 0x4e2, 'xor.b #40, r3h', IF_B, () ),
        ( '1543', 0x4e4, 'xor.b r4h, r3h', IF_B, () ),
        ( '79434715', 0x4e6, 'or.w #4715, r3', IF_W, () ),
        ( '6543', 0x4ea, 'xor.w r4, r3', IF_W, () ),
        ( '7A5300047145', 0x4ec, 'xor.l #47145, er3', IF_L, () ),
        ( '01F06543', 0x4f2, 'xor.l er4, er3', IF_L, () ),
        ( '0540', 0x4f6, 'xorc #40, ccr', 0, () ),
        ( '01410540', 0x4f8, 'xorc #40, exr', 0, () ),
        ]

class H8InstrTest(unittest.TestCase):
    def test_envi_h8_assorted_instrs(self):
        global instrs

        #archmod = envi.getArchModule("h8")
        vw = vivisect.VivWorkspace()
        vw.setMeta("Architecture", "h8")
        vw.addMemoryMap(0, 7, 'firmware', '\xff' * 16384*1024)
        vw.addMemoryMap(0x400000, 7, 'firmware', '\xff' * 16384*1024)
        emu = vw.getEmulator()
        emu.logread = emu.logwrite = True

        badcount = 0
        goodcount = 0

        #emu = archmod.getEmulator()
        #emu.addMemoryMap(0, 7, 'firmware', '\xff' * 16384*1024)
        #emu.addMemoryMap(0x400000, 7, 'firmware', '\xff' * 16384*1024)

        for bytez, va, reprOp, iflags, emutests in instrs:
            #op = archmod.archParseOpcode(bytez.decode('hex'), 0, va)
            op = vw.arch.archParseOpcode(bytez.decode('hex'), 0, va)
            redoprepr = repr(op).replace(' ','').lower()
            redgoodop = reprOp.replace(' ','').lower()
            if redoprepr != redgoodop:
                print("FAILED to decode instr:  %.8x %s - should be: %s  - is: %s" % \
                         ( va, bytez, reprOp, repr(op) ) )
                badcount += 1
                raise Exception("FAILED to decode instr:  %.8x %s - should be: %s  - is: %s" % \
                         ( va, bytez, reprOp, repr(op) ) )
            self.assertEqual((bytez, redoprepr, op.iflags), (bytez, redgoodop, iflags))

            #print goodcount, op

            # test some things
            if not len(emutests):
                # if we don't have tests, let's just run it in the emulator anyway and see if things break
                if not self.validateEmulation(emu, op, (), ()):
                    goodcount += 1
                else:
                    print( "FAILED emulation:  %s" % op )
                    badcount += 1

            else:
                for tdata in emutests:  # dict with 'setup' and 'tests' as keys
                    setup = tdata.get('setup', ())
                    tests = tdata.get('tests', ())
                    if not self.validateEmulation(emu, op, setup, tests):
                        goodcount += 1
                    else:
                        print( "FAILED emulation:  %s" % op )
                        badcount += 1

        print( "Failed Instruction Count: %d" % badcount )
        self.assertEqual(badcount, 0)
    #FIXME: test emuluation as well.
            

        op = vw.arch.archParseOpcode('12C3'.decode('hex'))
        #rotl.b #2, r3h
        print( op, hex(0x7a) )
        emu.setRegisterByName('r3h', 0x7a)
        emu.executeOpcode(op)
        print( hex(emu.getRegisterByName('r3h')), emu.getFlag(CCR_C) )
        #0xef False

        op = vw.arch.archParseOpcode('1283'.decode('hex'))
        #rotl.b #2, r3h
        print( op, hex(0x7a) )
        emu.setRegisterByName('r3h', 0x7a)
        emu.executeOpcode(op)
        print( hex(emu.getRegisterByName('r3h')), emu.getFlag(CCR_C) )
        #0xef False

        op = vw.arch.archParseOpcode('13C3'.decode('hex'));\
        #rotr.b #2, r3h
        print( op, hex(0x7a) )
        emu.setRegisterByName('r3h', 0x7a);\
        emu.executeOpcode(op);\
        print( hex(emu.getRegisterByName('r3h')), emu.getFlag(CCR_C) )
        #0x7a False

        op = vw.arch.archParseOpcode('1383'.decode('hex'));\
        #rotr.b #2, r3h
        print( op, hex(0x7a) )
        emu.setRegisterByName('r3h', 0x7a);\
        emu.executeOpcode(op);\
        print( hex(emu.getRegisterByName('r3h')), emu.getFlag(CCR_C) )
        #0x7a False

    def validateEmulation(self, emu, op, setters, tests):
        # first set any environment stuff necessary
        ## defaults
        emu.setRegister(REG_ER3, 0x414141)
        emu.setRegister(REG_ER4, 0x444444)
        emu.setRegister(REG_ER5, 0x454545)
        emu.setRegister(REG_ER6, 0x464646)
        emu.setRegister(REG_SP, 0x450000)

        ## special cases
        for tgt, val in setters:
            try:
                # try register first
                emu.setRegisterByName(tgt, val)
            except e_reg.InvalidRegisterName, e:
                # it's not a register
                if type(tgt) == str and tgt.startswith("CCR_"):
                    # it's a flag
                    emu.setFlag(eval(tgt), val)
                elif type(tgt) in (long, int):
                    # it's an address
                    emu.writeMemValue(tgt, val, 1) # limited to 1-byte writes currently
                else:
                    print( "Funkt up Setting:  %s = 0x%x" % (tgt, val) )

        emu.executeOpcode(op)

        # do tests
        success = 1
        for tgt, val in tests:
            try:
                # try register first
                testval = emu.getRegisterByName(tgt)
                if testval == val:
                    #print("SUCCESS: %s  ==  0x%x" % (tgt, val))
                    continue
                success = 0
                print("FAILED(reg): %s  !=  0x%x (observed: 0x%x)" % (tgt, val, testval))

            except e_reg.InvalidRegisterName, e:
                # it's not a register
                if type(tgt) == str and tgt.startswith("CCR_"):
                    # it's a flag
                    testval = emu.getFlag(eval(tgt)) 
                    if testval == val:
                        #print("SUCCESS: %s  ==  0x%x" % (tgt, val))
                        continue
                    success = 0
                    print("FAILED(flag): %s  !=  0x%x (observed: 0x%x)" % (tgt, val, testval))

                elif type(tgt) in (long, int):
                    # it's an address
                    testval = emu.readMemValue(tgt, 1)
                    if testval == val:
                        #print("SUCCESS: 0x%x  ==  0x%x" % (tgt, val))
                        continue
                    success = 0
                    print("FAILED(mem): 0x%x  !=  0x%x (observed: 0x%x)" % (tgt, val, testval))

                else:
                    print( "Funkt up test: %s == %s" % (tgt, val) )

        # do some read/write tracking/testing
        #print emu.curpath
        if len(emu.curpath[2]['readlog']):
            outstr = emu.curpath[2]['readlog']
            if len(outstr) > 10000: outstr = outstr[:10000]
            print( repr(op) + '\t\tRead: ' + repr(outstr) )
        if len(emu.curpath[2]['writelog']):
            outstr = emu.curpath[2]['writelog']
            if len(outstr) > 10000: outstr = outstr[:10000]
            print( repr(op) + '\t\tWrite: '+ repr(outstr) )
        emu.curpath[2]['readlog'] = []
        emu.curpath[2]['writelog'] = []

        return not success

    def test_parsers_rudimentary(self, buf = 'ABCDEFGHIJKLMNOP', off=3, va=0x2544):
        val, = struct.unpack_from('>H', buf, off)

        for tsize in (1,2,4):
            p_i3_Rd(va, val, buf, off, tsize)
            p_i3_aERd(va, val, buf, off, tsize) 
            p_i3_aAA8(va, val, buf, off, tsize) 
            p_i8_CCR(va, val, buf, off, tsize) 
            p_i8_Rd(va, val, buf, off, tsize) 
            p_i16_Rd(va, val, buf, off, tsize) 
            p_i32_ERd(va, val, buf, off, tsize) 
            p_Rd(va, val, buf, off, tsize) 
            p_Rs_Rd(va, val, buf, off, tsize)  
            p_Rs_Rd_4b(va, val, buf, off, tsize)  
            p_Rs_ERd(va, val, buf, off, tsize)  
            p_Rs_ERd_4b(va, val, buf, off, tsize)  
            p_ERd(va, val, buf, off, tsize)  
            p_ERs_ERd(va, val, buf, off, tsize)  
            p_Rn_Rd(va, val, buf, off, tsize)  
            p_Rn_aERd(va, val, buf, off, tsize)  
            p_Rn_aAA8(va, val, buf, off, tsize)  
            p_aERn(va, val, buf, off, tsize)  
            p_aAA24(va, val, buf, off, tsize)  
            p_aaAA8(va, val, buf, off, tsize)  
            p_disp8(va, val, buf, off, tsize)  
            p_disp16(va, val, buf, off, tsize)  
            p_nooperands(va, val, buf, off, tsize) 

        h8m = envi.getArchModule('h8')      

        for instr in raw_instrs:
            inst = instr[0]
            op = h8m.archParseOpcode(inst, 0, 0x50)
            print( "%26s %s" % (instr[0].encode('hex'), op) )
            if len(op) != len(inst):
                #raise Exception(" LENGTH FAILURE:  expected: %d  real: %d  '%s'" % (len(inst), len(op), inst.encode('hex')))
                print(" LENGTH FAILURE:  expected: %d  real: %d  '%s'" % (len(inst), len(op), inst.encode('hex')))



def generateTestInfo(ophexbytez='6e'):
    h8 = e_h8.H8Module()
    opbytez = ophexbytez
    op = h8.archParseOpcode(opbytez.decode('hex'), 0, 0x4000)
    print( "opbytez = '%s'\noprepr = '%s'"%(opbytez,repr(op)) )
    opvars=vars(op)
    opers = opvars.pop('opers')
    print( "opcheck = ",repr(opvars) )

    opersvars = []
    for x in range(len(opers)):
        opervars = vars(opers[x])
        opervars.pop('_dis_regctx')
        opersvars.append(opervars)

    print( "opercheck = %s" % (repr(opersvars)) )



raw_instrs = [
    ('8340'.decode('hex'), ),
    ('0832'.decode('hex'), ),
    ('79134715'.decode('hex'), ),
    ('0943'.decode('hex'), ),
    ('7a1300047145'.decode('hex'), ),
    ('0aa3'.decode('hex'), ),
    ('0b03'.decode('hex'), ),
    ('0b83'.decode('hex'), ),
    ('0b93'.decode('hex'), ),
    ('9340'.decode('hex'), ),
    ('0e43'.decode('hex'), ),
    ('e340'.decode('hex'), ),
    ('1643'.decode('hex'), ),
    ('79634715'.decode('hex'), ),
    ('6643'.decode('hex'), ),
    ('7a6300047145'.decode('hex'), ),
    ('01f06643'.decode('hex'), ),
    ('0640'.decode('hex'), ),
    ('01410640'.decode('hex'), ),
    ('7643'.decode('hex'), ),
    ('7c307640'.decode('hex'), ),
    ('7e477640'.decode('hex'), ),
    ('6a1047157640'.decode('hex'), ),
    ('6a30000471457640'.decode('hex'), ),
    ('4040'.decode('hex'), ),
    ('58004715'.decode('hex'), ),
    ('4150'.decode('hex'), ),
    ('58104715'.decode('hex'), ),
    ('4240'.decode('hex'), ),
    ('58204715'.decode('hex'), ),
    ('4340'.decode('hex'), ),
    ('58304715'.decode('hex'), ),
    ('4440'.decode('hex'), ),
    ('58404715'.decode('hex'), ),
    ('4540'.decode('hex'), ),
    ('58504715'.decode('hex'), ),
    ('4640'.decode('hex'), ),
    ('58604715'.decode('hex'), ),
    ('4740'.decode('hex'), ),
    ('58704715'.decode('hex'), ),
    ('4840'.decode('hex'), ),
    ('58804715'.decode('hex'), ),
    ('4940'.decode('hex'), ),
    ('58904715'.decode('hex'), ),
    ('4a40'.decode('hex'), ),
    ('58a04715'.decode('hex'), ),
    ('4b40'.decode('hex'), ),
    ('58b04715'.decode('hex'), ),
    ('4c40'.decode('hex'), ),
    ('58c04715'.decode('hex'), ),
    ('4d40'.decode('hex'), ),
    ('58d04715'.decode('hex'), ),
    ('4e40'.decode('hex'), ),
    ('58e04715'.decode('hex'), ),
    ('4f40'.decode('hex'), ),
    ('58f04715'.decode('hex'), ),
    ('7243'.decode('hex'), ),
    ('7d307240'.decode('hex'), ),
    ('7f407240'.decode('hex'), ),
    ('6a1847157240'.decode('hex'), ),
    ('6a38000471457240'.decode('hex'), ),
    ('6243'.decode('hex'), ),
    ('7d306240'.decode('hex'), ),
    ('7f406240'.decode('hex'), ),
    ('6a1847156240'.decode('hex'), ),
    ('6a38000471456240'.decode('hex'), ),
    ('76c3'.decode('hex'), ),
    ('7c3076c0'.decode('hex'), ),
    ('7e4076c0'.decode('hex'), ),
    ('6a10471576c0'.decode('hex'), ),
    ('6a300004714576c0'.decode('hex'), ),
    ('77c3'.decode('hex'), ),
    ('7c3077c0'.decode('hex'), ),
    ('7e4077c0'.decode('hex'), ),
    ('6a10471577c0'.decode('hex'), ),
    ('6a300004714577c0'.decode('hex'), ),
    ('74c3'.decode('hex'), ),
    ('7c3074c0'.decode('hex'), ),
    ('7e4074c0'.decode('hex'), ),
    ('6a10471574c0'.decode('hex'), ),
    ('6a300004714574c0'.decode('hex'), ),
    ('7d3067c0'.decode('hex'), ),
    ('7f4067c0'.decode('hex'), ),
    ('6a18471567c0'.decode('hex'), ),
    ('6a380004714567c0'.decode('hex'), ),
    ('75c3'.decode('hex'), ),
    ('7c3075c0'.decode('hex'), ),
    ('7e4075c0'.decode('hex'), ),
    ('6a10471575c0'.decode('hex'), ),
    ('6a300004714575c0'.decode('hex'), ),
    ('7743'.decode('hex'), ),
    ('7c307740'.decode('hex'), ),
    ('7e407740'.decode('hex'), ),
    ('6a1047157740'.decode('hex'), ),
    ('6a30000471457740'.decode('hex'), ),
    ('7143'.decode('hex'), ),
    ('7d307140'.decode('hex'), ),
    ('7f407140'.decode('hex'), ),
    ('6a1847157140'.decode('hex'), ),
    ('6a38000471457140'.decode('hex'), ),
    ('6143'.decode('hex'), ),
    ('7d306140'.decode('hex'), ),
    ('7f406140'.decode('hex'), ),
    ('6a1847156140'.decode('hex'), ),
    ('6a38000471456140'.decode('hex'), ),
    ('7443'.decode('hex'), ),
    ('7c307440'.decode('hex'), ),
    ('7e407440'.decode('hex'), ),
    ('6a1047157440'.decode('hex'), ),
    ('6a30000471457440'.decode('hex'), ),
    ('7043'.decode('hex'), ),
    ('7d307040'.decode('hex'), ),
    ('7f407040'.decode('hex'), ),
    ('6a1847157040'.decode('hex'), ),
    ('6a38000471457040'.decode('hex'), ),
    ('6043'.decode('hex'), ),
    ('7d306040'.decode('hex'), ),
    ('7f406040'.decode('hex'), ),
    ('6a1847156040'.decode('hex'), ),
    ('6a38000471456040'.decode('hex'), ),
    ('5542'.decode('hex'), ),
    ('5c004242'.decode('hex'), ),
    ('6743'.decode('hex'), ),
    ('7d306740'.decode('hex'), ),
    ('7f406740'.decode('hex'), ),
    ('6a1847156740'.decode('hex'), ),
    ('6a38000471456740'.decode('hex'), ),
    ('7343'.decode('hex'), ),
    ('7c307340'.decode('hex'), ),
    ('7e407340'.decode('hex'), ),
    ('6a1047157340'.decode('hex'), ),
    ('6a30000471457340'.decode('hex'), ),
    ('6343'.decode('hex'), ),
    ('7c306340'.decode('hex'), ),
    ('7e406340'.decode('hex'), ),
    ('6a1047156340'.decode('hex'), ),
    ('6a30000471456340'.decode('hex'), ),
    ('7543'.decode('hex'), ),
    ('7c307540'.decode('hex'), ),
    ('7e407540'.decode('hex'), ),
    ('6a1047157540'.decode('hex'), ),
    ('6a30000471457540'.decode('hex'), ),
    ('a340'.decode('hex'), ),
    ('1c43'.decode('hex'), ),
    ('79234715'.decode('hex'), ),
    ('1d43'.decode('hex'), ),
    ('7a2300047145'.decode('hex'), ),
    ('1fc3'.decode('hex'), ),
    ('0f03'.decode('hex'), ),
    ('1f03'.decode('hex'), ),
    ('1a03'.decode('hex'), ),
    ('1b53'.decode('hex'), ),
    ('1bd3'.decode('hex'), ),
    ('1b73'.decode('hex'), ),
    ('1bf3'.decode('hex'), ),
    ('01d05143'.decode('hex'), ),
    ('01d05343'.decode('hex'), ),
    ('5143'.decode('hex'), ),
    ('5343'.decode('hex'), ),
    ('7b5c598f'.decode('hex'), ),
    ('7bd4598f'.decode('hex'), ),
    ('17d3'.decode('hex'), ),
    ('17f3'.decode('hex'), ),
    ('1753'.decode('hex'), ),
    ('1773'.decode('hex'), ),
    ('0a03'.decode('hex'), ),
    ('0b53'.decode('hex'), ),
    ('0bd3'.decode('hex'), ),
    ('0b73'.decode('hex'), ),
    ('0bf3'.decode('hex'), ),
    ('5940'.decode('hex'), ),
    ('5a047145'.decode('hex'), ),
    ('5b41'.decode('hex'), ),
    ('5d40'.decode('hex'), ),
    ('5e047145'.decode('hex'), ),
    ('5f41'.decode('hex'), ),
    ('0740'.decode('hex'), ),
    ('01410740'.decode('hex'), ),
    ('0304'.decode('hex'), ),
    ('0314'.decode('hex'), ),
    ('01406940'.decode('hex'), ),
    ('01416940'.decode('hex'), ),
    ('01406f404715'.decode('hex'), ),
    ('01416f404715'.decode('hex'), ),
    ('014078406b2000047145'.decode('hex'), ),
    ('014178406b2000047145'.decode('hex'), ),
    ('01406d40'.decode('hex'), ),
    ('01416d40'.decode('hex'), ),
    ('01406b004715'.decode('hex'), ),
    ('01416b004715'.decode('hex'), ),
    ('01406b2000047145'.decode('hex'), ),
    ('01416b2000047145'.decode('hex'), ),
    ('01106d75'.decode('hex'), ),
    ('01206d75'.decode('hex'), ),
    ('01306d75'.decode('hex'), ),
    ('f340'.decode('hex'), ),
    ('0c43'.decode('hex'), ),
    ('6843'.decode('hex'), ),
    ('6e434715'.decode('hex'), ),
    ('78406a2300047145'.decode('hex'), ),
    ('6c43'.decode('hex'), ),
    ('2340'.decode('hex'), ),
    ('6a034715'.decode('hex'), ),
    ('78306a2300047145'.decode('hex'), ),
    ('6cb4'.decode('hex'), ),
    ('3440'.decode('hex'), ),
    ('6a844715'.decode('hex'), ),
    ('6aa400047145'.decode('hex'), ),
    ('79044715'.decode('hex'), ),
    ('0d43'.decode('hex'), ),
    ('6943'.decode('hex'), ),
    ('6f434715'.decode('hex'), ),
    ('78406b2300047145'.decode('hex'), ),
    ('6d43'.decode('hex'), ),
    ('6b034715'.decode('hex'), ),
    ('6b2300047145'.decode('hex'), ),
    ('69b4'.decode('hex'), ),
    ('6fb44715'.decode('hex'), ),
    ('78306ba400047145'.decode('hex'), ),
    ('6db4'.decode('hex'), ),
    ('6b844715'.decode('hex'), ),
    ('6ba400047145'.decode('hex'), ),
    ('7a0300047145'.decode('hex'), ),
    ('0fc3'.decode('hex'), ),
    ('01006943'.decode('hex'), ),
    ('01006f434715'.decode('hex'), ),
    ('010078406b2300047145'.decode('hex'), ),
    ('01006d43'.decode('hex'), ),
    ('01006b034715'.decode('hex'), ),
    ('01006b2300047145'.decode('hex'), ),
    ('010069b4'.decode('hex'), ),
    ('01006fb44715'.decode('hex'), ),
    ('010078306ba400047145'.decode('hex'), ),
    ('01006db4'.decode('hex'), ),
    ('01006b844715'.decode('hex'), ),
    ('01006ba400047145'.decode('hex'), ),
    ('01c05043'.decode('hex'), ),
    ('01c05243'.decode('hex'), ),
    ('5043'.decode('hex'), ),
    ('5243'.decode('hex'), ),
    ('1783'.decode('hex'), ),
    ('1793'.decode('hex'), ),
    ('17b3'.decode('hex'), ),
    ('0000'.decode('hex'), ),
    ('1703'.decode('hex'), ),
    ('1713'.decode('hex'), ),
    ('1733'.decode('hex'), ),
    ('c340'.decode('hex'), ),
    ('1443'.decode('hex'), ),
    ('79434715'.decode('hex'), ),
    ('6443'.decode('hex'), ),
    ('7a4300047145'.decode('hex'), ),
    ('01f06443'.decode('hex'), ),
    ('0440'.decode('hex'), ),
    ('01410440'.decode('hex'), ),
    ('6d74'.decode('hex'), ),
    ('01006d74'.decode('hex'), ),
    ('6df4'.decode('hex'), ),
    ('01006df4'.decode('hex'), ),
    ('1283'.decode('hex'), ),
    ('12c3'.decode('hex'), ),
    ('1293'.decode('hex'), ),
    ('12d3'.decode('hex'), ),
    ('12b3'.decode('hex'), ),
    ('12f3'.decode('hex'), ),
    ('1383'.decode('hex'), ),
    ('13c3'.decode('hex'), ),
    ('1393'.decode('hex'), ),
    ('13d3'.decode('hex'), ),
    ('13b3'.decode('hex'), ),
    ('13f3'.decode('hex'), ),
    ('1203'.decode('hex'), ),
    ('1243'.decode('hex'), ),
    ('1213'.decode('hex'), ),
    ('1253'.decode('hex'), ),
    ('1233'.decode('hex'), ),
    ('1273'.decode('hex'), ),
    ('1303'.decode('hex'), ),
    ('1343'.decode('hex'), ),
    ('1313'.decode('hex'), ),
    ('1353'.decode('hex'), ),
    ('1333'.decode('hex'), ),
    ('1373'.decode('hex'), ),
    ('5670'.decode('hex'), ),
    ('5470'.decode('hex'), ),
    ('1083'.decode('hex'), ),
    ('10c3'.decode('hex'), ),
    ('1093'.decode('hex'), ),
    ('10d3'.decode('hex'), ),
    ('10b3'.decode('hex'), ),
    ('10f3'.decode('hex'), ),
    ('1183'.decode('hex'), ),
    ('11c3'.decode('hex'), ),
    ('1193'.decode('hex'), ),
    ('11d3'.decode('hex'), ),
    ('11b3'.decode('hex'), ),
    ('11f3'.decode('hex'), ),
    ('1003'.decode('hex'), ),
    ('1043'.decode('hex'), ),
    ('1013'.decode('hex'), ),
    ('1053'.decode('hex'), ),
    ('1033'.decode('hex'), ),
    ('1073'.decode('hex'), ),
    ('1103'.decode('hex'), ),
    ('1143'.decode('hex'), ),
    ('1113'.decode('hex'), ),
    ('1153'.decode('hex'), ),
    ('1133'.decode('hex'), ),
    ('1173'.decode('hex'), ),
    ('0180'.decode('hex'), ),
    ('0203'.decode('hex'), ),
    ('0213'.decode('hex'), ),
    ('014069b0'.decode('hex'), ),
    ('014169b0'.decode('hex'), ),
    ('01406fb04715'.decode('hex'), ),
    ('01416fb04715'.decode('hex'), ),
    ('014078306ba000047145'.decode('hex'), ),
    ('014178306ba000047145'.decode('hex'), ),
    ('01406d30'.decode('hex'), ),
    ('01416d30'.decode('hex'), ),
    ('01406b804715'.decode('hex'), ),
    ('01416b804715'.decode('hex'), ),
    ('01406ba000047145'.decode('hex'), ),
    ('01416ba000047145'.decode('hex'), ),
    ('01106df4'.decode('hex'), ),
    ('01206df4'.decode('hex'), ),
    ('01306df4'.decode('hex'), ),
    ('1843'.decode('hex'), ),
    ('79334715'.decode('hex'), ),
    ('1943'.decode('hex'), ),
    ('7a3300047145'.decode('hex'), ),
    ('1ac3'.decode('hex'), ),
    ('1b03'.decode('hex'), ),
    ('1b83'.decode('hex'), ),
    ('1b93'.decode('hex'), ),
    ('b340'.decode('hex'), ),
    ('1e43'.decode('hex'), ),
    ('01e07b3c'.decode('hex'), ),
    ('5730'.decode('hex'), ),
    ('d340'.decode('hex'), ),
    ('1543'.decode('hex'), ),
    ('79434715'.decode('hex'), ),
    ('6543'.decode('hex'), ),
    ('7a5300047145'.decode('hex'), ),
    ('01f06543'.decode('hex'), ),
    ('0540'.decode('hex'), ),
    ('01410540'.decode('hex'), ),
    ]


