
import os
import PE
import vstruct
import vivisect
import PE.carve as pe_carve
import cStringIO as StringIO
import vivisect.parsers as v_parsers

# Steal symbol parsing from vtrace
import vtrace
import vtrace.platforms.win32 as vt_win32

import envi
import envi.memory as e_mem
import envi.symstore.symcache as e_symcache

from vivisect.const import *

# PE Machine field values
#0x14d   Intel i860
#0x14c   Intel I386 (same ID used for 486 and 586)
#0x162   MIPS R3000
#0x166   MIPS R4000
#0x183   DEC Alpha AXP

def parseFile(vw, filename):
    pe = PE.PE(file(filename,"rb"))
    return loadPeIntoWorkspace(vw, pe, filename)

def parseBytes(vw, bytes):
    fd = StringIO.StringIO(bytes)
    fd.seek(0)
    pe = PE.PE(fd)
    return loadPeIntoWorkspace(vw, pe, filename=filename)

def parseMemory(vw, memobj, base):
    pe = PE.peFromMemoryObject(memobj, base)
    mapbase, mapsize, perms, fname = memobj.getMemoryMap(base)
    #FIXME does the PE's load address get fixedup on rebase?
    return loadPeIntoWorkspace(vw, pe, fname)

def parseFd(vw, fd, filename=None):
    fd.seek(0)
    pe = PE.PE(fd)
    return loadPeIntoWorkspace(vw, pe, filename=filename)

arch_names = {
    PE.IMAGE_FILE_MACHINE_I386:'i386',
    PE.IMAGE_FILE_MACHINE_AMD64:'amd64',
}

defcalls = {
    'i386':'cdecl',
    'amd64':'msx64call',
}

# map PE relocation types to vivisect types where possible
relmap = {
    PE.IMAGE_REL_BASED_HIGHLOW:vivisect.RTYPE_BASERELOC,
}

def loadPeIntoWorkspace(vw, pe, filename=None):

    mach = pe.IMAGE_NT_HEADERS.FileHeader.Machine

    arch = arch_names.get(mach)
    if arch == None:
        raise Exception("Machine %.4x is not supported for PE!" % mach )

    vw.setMeta('Architecture', arch)
    vw.setMeta('Format', 'pe')

    platform = 'windows'

    # Drivers are platform "winkern" so impapi etc works
    subsys = pe.IMAGE_NT_HEADERS.OptionalHeader.Subsystem
    if subsys == PE.IMAGE_SUBSYSTEM_NATIVE:
        platform = 'winkern'

    vw.setMeta('Platform', platform)

    defcall = defcalls.get(arch)
    if defcall:
        vw.setMeta("DefaultCall", defcall)

    # Set ourselvs up for extended windows binary analysis

    baseaddr = pe.IMAGE_NT_HEADERS.OptionalHeader.ImageBase
    entry = pe.IMAGE_NT_HEADERS.OptionalHeader.AddressOfEntryPoint + baseaddr
    entryrva = entry - baseaddr

    codebase = pe.IMAGE_NT_HEADERS.OptionalHeader.BaseOfCode
    codesize = pe.IMAGE_NT_HEADERS.OptionalHeader.SizeOfCode
    codervamax = codebase+codesize

    fvivname = filename

    # This will help linkers with files that are re-named
    dllname = pe.getDllName()
    if dllname != None:
        fvivname = dllname

    if fvivname == None:
        fvivname = "pe_%.8x" % baseaddr

    fhash = "unknown hash"
    if os.path.exists(filename):
        fhash = v_parsers.md5File(filename)

    fname = vw.addFile(fvivname.lower(), baseaddr, fhash)

    symhash = e_symcache.symCacheHashFromPe(pe)
    vw.setFileMeta(fname, 'SymbolCacheHash', symhash)

    # Add file version info if VS_VERSIONINFO has it
    vs = pe.getVS_VERSIONINFO()
    if vs != None:
        vsver = vs.getVersionValue('FileVersion')
        if vsver != None and len(vsver):
            # add check to split seeing samples with spaces and nothing else..
            parts = vsver.split()
            if len(parts):
                vsver = vsver.split()[0]
                vw.setFileMeta(fname, 'Version', vsver)

    # Setup some va sets used by windows analysis modules
    vw.addVaSet("Library Loads", (("Address", VASET_ADDRESS),("Library", VASET_STRING)))
    vw.addVaSet('pe:ordinals', (('Address', VASET_ADDRESS),('Ordinal',VASET_INTEGER)))

    # SizeOfHeaders spoofable...
    curr_offset = pe.IMAGE_DOS_HEADER.e_lfanew + len(pe.IMAGE_NT_HEADERS) 
    
    secsize = len(vstruct.getStructure("pe.IMAGE_SECTION_HEADER"))
    
    sec_offset = pe.IMAGE_DOS_HEADER.e_lfanew + 4 + len(pe.IMAGE_NT_HEADERS.FileHeader) +  pe.IMAGE_NT_HEADERS.FileHeader.SizeOfOptionalHeader 
    
    if sec_offset != curr_offset:
        header_size = sec_offset + pe.IMAGE_NT_HEADERS.FileHeader.NumberOfSections * secsize
    else:
        header_size = pe.IMAGE_DOS_HEADER.e_lfanew + len(pe.IMAGE_NT_HEADERS) + pe.IMAGE_NT_HEADERS.FileHeader.NumberOfSections * secsize

    # Add the first page mapped in from the PE header.
    header = pe.readAtOffset(0, header_size)


    secalign = pe.IMAGE_NT_HEADERS.OptionalHeader.SectionAlignment

    subsys_majver = pe.IMAGE_NT_HEADERS.OptionalHeader.MajorSubsystemVersion
    subsys_minver = pe.IMAGE_NT_HEADERS.OptionalHeader.MinorSubsystemVersion

    secrem = len(header) % secalign
    if secrem != 0:
        header += "\x00" * (secalign - secrem)

    vw.addMemoryMap(baseaddr, e_mem.MM_READ, fname, header)
    vw.addSegment(baseaddr, len(header), "PE_Header", fname)

    hstruct = vw.makeStructure(baseaddr, "pe.IMAGE_DOS_HEADER")
    magicaddr = hstruct.e_lfanew
    if vw.readMemory(baseaddr + magicaddr, 2) != "PE":
        raise Exception("We only support PE exe's")

    if not vw.isLocation( baseaddr + magicaddr ):
        padloc = vw.makePad(baseaddr + magicaddr, 4)

    ifhdr_va = baseaddr + magicaddr + 4
    ifstruct = vw.makeStructure(ifhdr_va, "pe.IMAGE_FILE_HEADER")

    vw.makeStructure(ifhdr_va + len(ifstruct), "pe.IMAGE_OPTIONAL_HEADER")

    # get resource data directory
    ddir = pe.getDataDirectory(PE.IMAGE_DIRECTORY_ENTRY_RESOURCE)
    loadrsrc = vw.config.viv.parsers.pe.loadresources
    carvepes = vw.config.viv.parsers.pe.carvepes

    deaddirs = [PE.IMAGE_DIRECTORY_ENTRY_EXPORT,
                PE.IMAGE_DIRECTORY_ENTRY_IMPORT,
                PE.IMAGE_DIRECTORY_ENTRY_RESOURCE,
                PE.IMAGE_DIRECTORY_ENTRY_EXCEPTION,
                PE.IMAGE_DIRECTORY_ENTRY_SECURITY,
                PE.IMAGE_DIRECTORY_ENTRY_BASERELOC,
                PE.IMAGE_DIRECTORY_ENTRY_DEBUG,
                PE.IMAGE_DIRECTORY_ENTRY_COPYRIGHT,
                PE.IMAGE_DIRECTORY_ENTRY_ARCHITECTURE,
                PE.IMAGE_DIRECTORY_ENTRY_GLOBALPTR,
                PE.IMAGE_DIRECTORY_ENTRY_LOAD_CONFIG,
                PE.IMAGE_DIRECTORY_ENTRY_BOUND_IMPORT,
                PE.IMAGE_DIRECTORY_ENTRY_IAT,
                PE.IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT,
                PE.IMAGE_DIRECTORY_ENTRY_COM_DESCRIPTOR]
    deadvas = [ddir.VirtualAddress]
    for datadir in deaddirs:
        d = pe.getDataDirectory(datadir)
        if d.VirtualAddress:
            deadvas.append(d.VirtualAddress)

    for idx, sec in enumerate(pe.sections):
        mapflags = 0

        chars = sec.Characteristics
        if chars & PE.IMAGE_SCN_MEM_READ:
            mapflags |= e_mem.MM_READ

            isrsrc = ( sec.VirtualAddress == ddir.VirtualAddress )
            if isrsrc and not loadrsrc:
                continue

            # If it's for an older system, just about anything
            # is executable...
            if not vw.config.viv.parsers.pe.nx and subsys_majver < 6 and not isrsrc:
                mapflags |= e_mem.MM_EXEC

        if chars & PE.IMAGE_SCN_MEM_READ:
            mapflags |= e_mem.MM_READ
        if chars & PE.IMAGE_SCN_MEM_WRITE:
            mapflags |= e_mem.MM_WRITE
        if chars & PE.IMAGE_SCN_MEM_EXECUTE:
            mapflags |= e_mem.MM_EXEC
        if chars & PE.IMAGE_SCN_CNT_CODE:
            mapflags |= e_mem.MM_EXEC


        secrva = sec.VirtualAddress
        secvsize = sec.VirtualSize
        secfsize = sec.SizeOfRawData
        secbase = secrva + baseaddr
        secname = sec.Name.strip("\x00")
        secrvamax = secrva + secvsize
    
        # If the section is part of BaseOfCode->SizeOfCode
        # force execute perms...
        if secrva >= codebase and secrva < codervamax:
            mapflags |= e_mem.MM_EXEC

        # If the entry point is in this section, force execute
        # permissions.
        if secrva <= entryrva and entryrva < secrvamax:
            mapflags |= e_mem.MM_EXEC

        if not vw.config.viv.parsers.pe.nx and subsys_majver < 6 and mapflags & e_mem.MM_READ:
            mapflags |= e_mem.MM_EXEC

        if sec.VirtualSize == 0 or sec.SizeOfRawData == 0:
            if idx+1 >= len(pe.sections):
                continue
            # fill the gap with null bytes.. 
            nsec = pe.sections[idx+1] 
            nbase = nsec.VirtualAddress + baseaddr

            plen = nbase - secbase 
            readsize = sec.SizeOfRawData if sec.SizeOfRawData < sec.VirtualSize else sec.VirtualSize
            secoff = pe.rvaToOffset(secrva)
            secbytes = pe.readAtOffset(secoff, readsize)
            secbytes += "\x00" * plen
            vw.addMemoryMap(secbase, mapflags, fname, secbytes)
            vw.addSegment(secbase, len(secbytes), secname, fname)

            # Mark dead data on resource and import data directories
            if sec.VirtualAddress in deadvas:
                vw.markDeadData(secbase, secbase+len(secbytes))

            #FIXME create a mask for this
            if not (chars & PE.IMAGE_SCN_CNT_CODE) and not (chars & PE.IMAGE_SCN_MEM_EXECUTE) and not (chars & PE.IMAGE_SCN_MEM_WRITE):
                vw.markDeadData(secbase, secbase+len(secbytes))
            continue
        
        # if SizeOfRawData is greater than VirtualSize we'll end up using VS in our read..
        if sec.SizeOfRawData < sec.VirtualSize:
            if sec.SizeOfRawData > pe.filesize: 
                continue
    
        plen = sec.VirtualSize - sec.SizeOfRawData          
    
        try:
            # According to http://code.google.com/p/corkami/wiki/PE#section_table if SizeOfRawData is larger than VirtualSize, VS is used..
            readsize = sec.SizeOfRawData if sec.SizeOfRawData < sec.VirtualSize else sec.VirtualSize

            secoff = pe.rvaToOffset(secrva)
            secbytes = pe.readAtOffset(secoff, readsize)
            secbytes += "\x00" * plen
            vw.addMemoryMap(secbase, mapflags, fname, secbytes)
            vw.addSegment(secbase, len(secbytes), secname, fname)

            # Mark dead data on resource and import data directories
            if sec.VirtualAddress in deadvas:
                vw.markDeadData(secbase, secbase+len(secbytes))

            #FIXME create a mask for this
            if not (chars & PE.IMAGE_SCN_CNT_CODE) and not (chars & PE.IMAGE_SCN_MEM_EXECUTE) and not (chars & PE.IMAGE_SCN_MEM_WRITE):
                vw.markDeadData(secbase, secbase+len(secbytes))

        except Exception, e:
            print("Error Loading Section (%s size:%d rva:%.8x offset: %d): %s" % (secname,secfsize,secrva,secoff,e))

    vw.addExport(entry, EXP_FUNCTION, '__entry', fname)
    vw.addEntryPoint(entry)

    # store the actual reloc section virtual address
    reloc_va = pe.getDataDirectory(PE.IMAGE_DIRECTORY_ENTRY_BASERELOC).VirtualAddress
    if reloc_va:
        reloc_va += baseaddr
    vw.setFileMeta(fname, "reloc_va", reloc_va)

    for rva,rtype in pe.getRelocations():

        # map PE reloc to VIV reloc ( or dont... )
        vtype = relmap.get(rtype)
        if vtype == None:
            continue

        vw.addRelocation(rva+baseaddr, vtype)

    for rva, lname, iname in pe.getImports():
        if vw.probeMemory(rva+baseaddr, 4, e_mem.MM_READ):
            vw.makeImport(rva+baseaddr, lname, iname)

    # Tell vivisect about ntdll functions that don't exit...
    vw.addNoReturnApi("ntdll.RtlExitUserThread")
    vw.addNoReturnApi("kernel32.ExitProcess")
    vw.addNoReturnApi("kernel32.ExitThread")
    vw.addNoReturnApi("kernel32.FatalExit")
    vw.addNoReturnApiRegex("^msvcr.*\._CxxThrowException$")
    vw.addNoReturnApiRegex("^msvcr.*\.abort$")
    vw.addNoReturnApi("ntoskrnl.KeBugCheckEx")

    exports = pe.getExports()
    for rva, ord, name in exports:
        eva = rva + baseaddr
        try:
            vw.setVaSetRow('pe:ordinals', (eva,ord))
            vw.addExport(eva, EXP_UNTYPED, name, fname)
            if vw.probeMemory(eva, 1, e_mem.MM_EXEC):
                vw.addEntryPoint(eva)
        except Exception, e:
            vw.vprint('addExport Failed: %s.%s (0x%.8x): %s' % (fname,name,eva,e))

    # Save off the ordinals...
    vw.setFileMeta(fname, 'ordinals', exports)

    fwds = pe.getForwarders()
    for rva, name, forwardname in fwds:
        vw.makeName(rva+baseaddr, "forwarder_%s.%s" % (fname, name))
        vw.makeString(rva+baseaddr)

    vw.setFileMeta(fname, 'forwarders', fwds)

    # Check For SafeSEH list...
    if pe.IMAGE_LOAD_CONFIG != None:

        vw.setFileMeta(fname, "SafeSEH", True)

        va = pe.IMAGE_LOAD_CONFIG.SEHandlerTable
        if va != 0:
            vw.makeName(va, "%s.SEHandlerTable" % fname)
            count = pe.IMAGE_LOAD_CONFIG.SEHandlerCount
            # RP BUG FIX - sanity check the count
            if count * 4 < pe.filesize and vw.isValidPointer(va):
                # XXX - CHEAP HACK for some reason we have binaries still thorwing issues.. 
                
                try:
                    # Just cheat and use the workspace with memory maps in it already
                    for h in vw.readMemoryFormat(va, "<%dP" % count):
                        sehva = baseaddr + h
                        vw.addEntryPoint(sehva)
                        #vw.hintFunction(sehva, meta={'SafeSEH':True})
                except:
                    vw.vprint("SEHandlerTable parse error")

    # Last but not least, see if we have symbol support and use it if we do
    if vt_win32.dbghelp:

        s = vt_win32.Win32SymbolParser(-1, filename, baseaddr)

        # We don't want exports or whatever because we already have them
        s.symopts |= vt_win32.SYMOPT_EXACT_SYMBOLS
        s.parse()

        # Add names for any symbols which are missing them
        for symname, symva, size, flags in s.symbols:

            if not vw.isValidPointer(symva):
                continue

            try:

                if vw.getName(symva) == None:
                    vw.makeName(symva, symname, filelocal=True)

            except Exception, e:
                vw.vprint("Symbol Load Error: %s" % e)

        # Also, lets set the locals/args name hints if we found any
        vw.setFileMeta(fname, 'PELocalHints', s._sym_locals)

    # if it has an EXCEPTION directory parse if it has the pdata
    edir = pe.getDataDirectory(PE.IMAGE_DIRECTORY_ENTRY_EXCEPTION)
    if edir.VirtualAddress and arch == 'amd64':
        va = edir.VirtualAddress + baseaddr
        vamax = va + edir.Size
        while va < vamax:
            f = vw.makeStructure(va, 'pe.IMAGE_RUNTIME_FUNCTION_ENTRY')
            if not vw.isValidPointer(baseaddr + f.UnwindInfoAddress):
                break

            # FIXME UNWIND_INFO *requires* DWORD alignment, how is it enforced?
            fva = f.BeginAddress + baseaddr
            uiva = baseaddr + f.UnwindInfoAddress
            # Possible method 1...
            #uiva = baseaddr + (f.UnwindInfoAddress & 0xfffffffc )

            # Possible method 2...
            #uirem = f.UnwindInfoAddress % 4
            #if uirem:
                #uiva += ( 4 - uirem )
            uinfo = vw.getStructure(uiva, 'pe.UNWIND_INFO')
            ver = uinfo.VerFlags & 0x7
            if ver != 1:
                vw.vprint('Unwind Info Version: %d (bailing on .pdata)' % ver)
                break

            flags = uinfo.VerFlags >> 3
            # Check if it's a function *block* rather than a function *entry*
            if not (flags & PE.UNW_FLAG_CHAININFO):
                vw.addEntryPoint(fva)

            va += len(f)

    # auto-mark embedded PEs as "dead data" to prevent code flow...
    if carvepes: 
        pe.fd.seek(0)
        fbytes = pe.fd.read()
        for offset, i in pe_carve.carve(fbytes, 1):
            # Found a sub-pe!
            subpe = pe_carve.CarvedPE(fbytes, offset, chr(i))
            pebytes = subpe.readAtOffset(0, subpe.getFileSize())
            rva = pe.offsetToRva(offset)
            vw.markDeadData(rva, rva+len(pebytes))

    return fname
