import allel
from collections import Counter
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

def get_effective_pred(prediction, chm_len, window_size, model_idx):
    """
    Maps SNP indices to window number to find predictions for those SNPs
    """

    # expanding prediction
    ext = np.repeat(prediction, window_size, axis=1)

    # handling remainder
    rem_len = chm_len-ext.shape[1]
    ext_rem = np.tile(prediction[:,-1], [rem_len,1]).T
    ext = np.concatenate([ext, ext_rem], axis=1)

    # return relevant positions
    return ext[:, model_idx]


def get_meta_data(chm, model_pos, query_pos, n_wind, wind_size, gen_map_df):
    """
    Transforms the predictions on a window level to a .msp file format.
        - chm: chromosome number
        - model_pos: physical positions of the model input SNPs in basepair units
        - query_pos: physical positions of the query input SNPs in basepair units
        - n_wind: number of windows in model
        - wind_size: size of each window in the model
        - genetic_map_file: the input genetic map file
    """

    model_chm_len = len(model_pos)
    
    # chm
    chm_array = [chm]*n_wind

    # start and end pyshical positions
    spos_idx = np.arange(0, model_chm_len, wind_size)[:-1]
    epos_idx = np.concatenate([np.arange(0, model_chm_len, wind_size)[1:-1],np.array([model_chm_len])])-1
    spos = model_pos[spos_idx]
    epos = model_pos[epos_idx]

    # start and end positions in cM (using linear interpolation, truncate ends of map file)
    end_pts = tuple(np.array(gen_map_df.pos_cm)[[0,-1]])
    f = interp1d(gen_map_df.pos, gen_map_df.pos_cm, fill_value=end_pts, bounds_error=False) 
    sgpos = np.round(f(spos),5)
    egpos = np.round(f(epos),5)

    # number of query snps in interval
    wind_index = [min(n_wind-1, np.where(q == sorted(np.concatenate([epos, [q]])))[0][0]) for q in query_pos]
    window_count = Counter(wind_index)
    n_snps = [window_count[w] for w in range(n_wind)]

    # Concat with prediction table
    meta_data = np.array([chm_array, spos, epos, sgpos, egpos, n_snps]).T
    meta_data_df = pd.DataFrame(meta_data)
    meta_data_df.columns = ["chm", "spos", "epos", "sgpos", "egpos", "n snps"]

    return meta_data_df

def get_samples_from_msp_df(msp_df):
    """Function for getting sample IDs from a pandas DF containing the output data"""

    # get all columns including sample names
    query_samples_dub = msp_df.columns[6:]

    # only keep 1 of maternal/paternal 
    single_ind_idx = np.arange(0,len(query_samples_dub),2)
    query_samples_sing = query_samples_dub[single_ind_idx]

    # remove the suffix
    query_samples = [qs[:-2] for qs in query_samples_sing]

    return query_samples
    
def write_msp(msp_prefix, meta_data, pred_labels, populations, query_samples):
    
    msp_data = np.concatenate([np.array(meta_data), pred_labels.T], axis=1).astype(str)
    
    with open(msp_prefix+".msp", 'w') as f:
        # first line (comment)
        f.write("#Subpopulation order/codes: ")
        f.write("\t".join([str(pop)+"="+str(i) for i, pop in enumerate(populations)])+"\n")
        # second line (comment/header)
        f.write("#"+"\t".join(meta_data.columns) + "\t")
        f.write("\t".join([str(s) for s in np.concatenate([[s+".0",s+".1"] for s in query_samples])])+"\n")
        # rest of the lines (data)
        for l in range(msp_data.shape[0]):
            f.write("\t".join(msp_data[l,:]))
            f.write("\n")

def write_fb(fb_prefix, meta_data, proba, ancestry, query_samples):
    
    n_rows = meta_data.shape[0]

    pp = np.round(np.mean(np.array(meta_data[["spos", "epos"]],dtype=int),axis=1)).astype(int)
    gp = np.mean(np.array(meta_data[["sgpos", "egpos"]],dtype=float),axis=1).astype(float)

    fb_meta_data = pd.DataFrame()
    fb_meta_data["chromosome"] = meta_data["chm"]
    fb_meta_data["physical position"] = pp
    fb_meta_data["genetic_position"]  = gp
    fb_meta_data["genetic_marker_index"] = np.repeat(".", n_rows)

    fb_prob_header = [":::".join([q,h,a]) for q in query_samples for h in ["hap1", "hap2"] for a in ancestry]
    fb_prob = np.swapaxes(proba,1,2).reshape(-1, n_rows).T
    fb_prob_df = pd.DataFrame(fb_prob)
    fb_prob_df.columns = fb_prob_header

    fb_df = pd.concat((fb_meta_data.reset_index(drop=True), fb_prob_df),axis=1)

    with open(fb_prefix+".fb", 'w') as f:
        # header
        f.write("#reference_panel_population:\t")
        f.write("\t".join(ancestry)+"\n")
        fb_df.to_csv(f, sep="\t", index=False)

    return
