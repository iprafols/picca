import scipy as sp
import sys
import fitsio
import glob


from picca.data import delta

def cov(da,we):

    mda = (da*we).sum(axis=0)
    swe = we.sum(axis=0)
    w = swe>0.
    mda[w] /= swe[w]

    wda = we*(da-mda)

    print("Computing cov...")

    co = wda.T.dot(wda)
    sswe = swe*swe[:,None]
    w = sswe>0.
    co[w] /= sswe[w]

    return co
def smooth_cov(da,we,rp,rt,drt=4,drp=4):

    co = cov(da,we)

    nda = da.shape[1]
    var = sp.diagonal(co)
    if sp.any(var==0.):
        print('ERROR: data has some empty bins, impossible to smooth')
        sys.exit()

    cor = co/sp.sqrt(var*var[:,None])

    cor_smooth = sp.zeros([nda,nda])

    dcor={}
    dncor={}

    for i in range(nda):
        sys.stderr.write("\rsmoothing {}".format(i))
        for j in range(i+1,nda):
            idrp = round(abs(rp[j]-rp[i])/drp)
            idrt = round(abs(rt[i]-rt[j])/drt)
            if not (idrp,idrt) in dcor:
                dcor[(idrp,idrt)]=0.
                dncor[(idrp,idrt)]=0

            dcor[(idrp,idrt)] +=cor[i,j]
            dncor[(idrp,idrt)] +=1

    for i in range(nda):
        cor_smooth[i,i]=1.
        for j in range(i+1,nda):
            idrp = round(abs(rp[j]-rp[i])/drp)
            idrt = round(abs(rt[i]-rt[j])/drt)
            cor_smooth[i,j]=dcor[(idrp,idrt)]/dncor[(idrp,idrt)]
            cor_smooth[j,i]=cor_smooth[i,j]


    sys.stderr.write("\n")
    co_smooth = cor_smooth * sp.sqrt(var*var[:,None])
    return co_smooth

def desi_from_truth_to_drq(truth,targets,drq,spectype="QSO"):
    '''
    Transform a desi truth.fits file and a
    desi targets.fits into a drq like file

    '''

    ## Truth table
    vac = fitsio.FITS(truth)

    w = sp.ones(vac[1]["TARGETID"][:].size).astype(bool)
    print(" start                 : nb object in cat = {}".format(w.sum()) )
    w &= sp.char.strip(vac[1]["TRUESPECTYPE"][:].astype(str))==spectype
    print(" and TRUESPECTYPE=={}  : nb object in cat = {}".format(spectype,w.sum()) )

    thid = vac[1]["TARGETID"][:][w]
    zqso = vac[1]["TRUEZ"][:][w]
    vac.close()
    ra = sp.zeros(thid.size)
    dec = sp.zeros(thid.size)
    plate = 1+sp.arange(thid.size)
    mjd = 1+sp.arange(thid.size)
    fid = 1+sp.arange(thid.size)

    ### Get RA and DEC from targets
    vac = fitsio.FITS(targets)
    thidTargets = vac[1]["TARGETID"][:]
    raTargets = vac[1]["RA"][:]
    decTargets = vac[1]["DEC"][:]
    vac.close()

    from_TARGETID_to_idx = {}
    for i,t in enumerate(thidTargets):
        from_TARGETID_to_idx[t] = i
    keys_from_TARGETID_to_idx = from_TARGETID_to_idx.keys()

    for i,t in enumerate(thid):
        if t not in keys_from_TARGETID_to_idx: continue
        idx = from_TARGETID_to_idx[t]
        ra[i] = raTargets[idx]
        dec[i] = decTargets[idx]
    if (ra==0.).sum()!=0 or (dec==0.).sum()!=0:
        w = ra!=0.
        w &= dec!=0.
        print(" and RA and DEC        : nb object in cat = {}".format(w.sum()))

        ra = ra[w]
        dec = dec[w]
        zqso = zqso[w]
        thid = thid[w]
        plate = plate[w]
        mjd = mjd[w]
        fid = fid[w]

    ### Save
    out = fitsio.FITS(drq,'rw',clobber=True)
    cols=[ra,dec,thid,plate,mjd,fid,zqso]
    names=['RA','DEC','THING_ID','PLATE','MJD','FIBERID','Z']
    out.write(cols,names=names)
    out.close()

    return

def desi_from_ztarget_to_drq(ztarget,drq,spectype="QSO"):
    '''
    Transform a desi truth.fits file and a
    desi targets.fits into a drq like file

    '''

    vac = fitsio.FITS(ztarget)

    ## Info of the primary observation
    thid  = vac[1]["TARGETID"][:]
    ra    = vac[1]["RA"][:]
    dec   = vac[1]["DEC"][:]
    zqso  = vac[1]["Z"][:]
    plate = 1+sp.arange(thid.size)
    mjd   = 1+sp.arange(thid.size)
    fid   = 1+sp.arange(thid.size)
    sptype = sp.char.strip(vac[1]["SPECTYPE"][:].astype(str))

    ## Sanity
    print(" start               : nb object in cat = {}".format(ra.size) )
    w = (vac[1]["ZWARN"][:]==0.)
    print(" and zwarn==0        : nb object in cat = {}".format(ra[w].size) )
    w = w & (sptype==spectype)
    print(" and spectype=={}    : nb object in cat = {}".format(spectype,ra[w].size) )

    ra    = ra[w]
    dec   = dec[w]
    zqso  = zqso[w]
    thid  = thid[w]
    plate = plate[w]
    mjd   = mjd[w]
    fid   = fid[w]

    vac.close()

    ### Save
    out = fitsio.FITS(drq,'rw',clobber=True)
    cols=[ra,dec,thid,plate,mjd,fid,zqso]
    names=['RA','DEC','THING_ID','PLATE','MJD','FIBERID','Z']
    out.write(cols,names=names)
    out.close()

    return
def desi_convert_transmission_to_delta_files(zcat,indir,outdir,lObs_min=3600.,lObs_max=5500.,lRF_min=1040.,lRF_max=1200.,dll=3.e-4,nspec=None):
    """Convert desi transmission files to picca delta files

    Args:
        zcat (str): path to the catalog of object to extract the transmission from
        indir (str): path to transmission files directory
        outdir (str): path to write delta files directory
        lObs_min (float) = 3600.: min observed wavelength in Angstrom
        lObs_max (float) = 5500.: max observed wavelength in Angstrom
        lRF_min (float) = 1040.: min Rest Frame wavelength in Angstrom
        lRF_max (float) = 1200.: max Rest Frame wavelength in Angstrom
        dll (float) = 3.e-4: size of the bins in log lambda
        nspec (int) = None: number of spectra, if 'None' use all

    Returns:
        None

    """

    ### Catalog of objects
    h = fitsio.FITS(zcat)
    zcat_thid = h[1]['TARGETID'][:]
    h.close()

    ### List of transmission files
    if len(indir)>8 and indir[-8:]=='.fits.gz':
        fi = glob.glob(indir)
    elif len(indir)>5 and indir[-5:]=='.fits':
        fi = glob.glob(indir)
    else:
        fi = glob.glob(indir+'/*.fits') + glob.glob(indir+'/*.fits.gz')
    fi = sp.sort(sp.array(fi))

    ### Stack the transmission
    lmin = sp.log10(lObs_min)
    lmax = sp.log10(lObs_max)
    nstack = int((lmax-lmin)/dll)+1
    T_stack = sp.zeros(nstack)
    n_stack = sp.zeros(nstack)

    deltas = {}

    ### Read
    for nf, f in enumerate(fi):
        sys.stderr.write("\rread {} of {} {}".format(nf,fi.size,sp.sum([ len(deltas[p]) for p in list(deltas.keys())])))
        h = fitsio.FITS(f)
        thid = h['METADATA']['MOCKID'][:]
        if sp.in1d(thid,zcat_thid).sum()==0:
            h.close()
            continue
        ra = h['METADATA']['RA'][:]*sp.pi/180.
        dec = h['METADATA']['DEC'][:]*sp.pi/180.
        z = h['METADATA']['Z'][:]
        ll = sp.log10(h['WAVELENGTH'].read())
        trans = h['TRANSMISSION'].read()
        nObj = z.size
        pixnum = h['METADATA'].read_header()['PIXNUM']

        if trans.shape[0]!=nObj:
            trans = trans.transpose()

        bins = sp.floor((ll-lmin)/dll+0.5).astype(int)
        tll = lmin + bins*dll
        lObs = (10**tll)*sp.ones(nObj)[:,None]
        lRF = (10**tll)/(1.+z[:,None])
        w = sp.zeros_like(trans).astype(int)
        w[ (lObs>=lObs_min) & (lObs<lObs_max) & (lRF>lRF_min) & (lRF<lRF_max) ] = 1
        nbPixel = sp.sum(w,axis=1)
        cut = nbPixel>=50
        cut &= sp.in1d(thid,zcat_thid)
        if cut.sum()==0:
            h.close()
            continue

        ra = ra[cut]
        dec = dec[cut]
        z = z[cut]
        thid = thid[cut]
        trans = trans[cut,:]
        w = w[cut,:]
        nObj = z.size
        h.close()

        deltas[pixnum] = []
        for i in range(nObj):
            tll = ll[w[i,:]>0]
            ttrans = trans[i,:][w[i,:]>0]

            bins = sp.floor((tll-lmin)/dll+0.5).astype(int)
            cll = lmin + sp.arange(nstack)*dll
            cfl = sp.bincount(bins,weights=ttrans,minlength=nstack)
            civ = sp.bincount(bins,minlength=nstack).astype(float)

            ww = civ>0.
            if ww.sum()<50: continue
            T_stack += cfl
            n_stack += civ
            cll = cll[ww]
            cfl = cfl[ww]/civ[ww]
            civ = civ[ww]
            deltas[pixnum].append(delta(thid[i],ra[i],dec[i],z[i],thid[i],thid[i],thid[i],cll,civ,None,cfl,1,None,None,None,None,None,None))
        if not nspec is None and sp.sum([ len(deltas[p]) for p in list(deltas.keys())])>=nspec: break

    print('\n')

    ### Get stacked transmission
    w = n_stack>0.
    T_stack[w] /= n_stack[w]

    ### Transform transmission to delta and store it
    for nf, p in enumerate(sorted(list(deltas.keys()))):
        sys.stderr.write("\rwrite {} of {} ".format(nf,len(list(deltas.keys()))))
        out = fitsio.FITS(outdir+'/delta-{}'.format(p)+'.fits.gz','rw',clobber=True)
        for d in deltas[p]:
            bins = sp.floor((d.ll-lmin)/dll+0.5).astype(int)
            d.de = d.de/T_stack[bins] - 1.
            d.we *= T_stack[bins]**2

            hd = {}
            hd['RA'] = d.ra
            hd['DEC'] = d.dec
            hd['Z'] = d.zqso
            hd['PMF'] = '{}-{}-{}'.format(d.plate,d.mjd,d.fid)
            hd['THING_ID'] = d.thid
            hd['PLATE'] = d.plate
            hd['MJD'] = d.mjd
            hd['FIBERID'] = d.fid
            hd['ORDER'] = d.order

            cols = [d.ll,d.de,d.we,sp.ones(d.ll.size)]
            names = ['LOGLAM','DELTA','WEIGHT','CONT']
            out.write(cols,names=names,header=hd,extname=str(d.thid))
        out.close()

    print('\n')

    return
def compute_ang_max(cosmo,rt_max,zmin,zmin2=None):
    '''
    Compute the maximum angle given by the maximum transverse
    separation the correlation should be calculated to
    '''

    if zmin2 is None:
        zmin2 = zmin

    rmin1 = cosmo.r_comoving(zmin)
    rmin2 = cosmo.r_comoving(zmin2)

    if rmin1+rmin2<rt_max:
        angmax = sp.pi
    else:
        angmax = 2.*sp.arcsin(rt_max/(rmin1+rmin2))

    return angmax
