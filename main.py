import numpy as np
import pandas as pd
import responsibly
from sklearn.model_selection import train_test_split

import argparse
from utils import mutual_information_2d
import matplotlib.pyplot as plt
import seaborn as sns; sns.set()
plt.style.use('seaborn')

parser = argparse.ArgumentParser(description='Configurations')
parser.add_argument('-n', type=int, default=20)
parser.add_argument('--repeats', type=int, default=5)
parser.add_argument('--dataset', choices=['adult', 'compas'], default='adult')
parser.add_argument('--model', choices=['LR', 'SVM', 'MLP'], default='LR')

args = parser.parse_args()

# import dataset
from datasets import *
if args.dataset == 'compas':
    X, Y, A = compas()
else:
    X, Y, A = adult()

# import models
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC
from sklearn.linear_model import LogisticRegression
models = {
    'LR' : LogisticRegression(solver='liblinear', fit_intercept=True),
    'SVM' : SVC(gamma='auto'),
    'MLP' : MLPClassifier(hidden_layer_sizes=(100,), random_state=1, max_iter=300)
}

# pipeline
def run(X, Y, A, repeats=5):
    accuracy = []
    dp, equal_tpr, equal_fpr, eo = [], [], [], []

    for i in range(repeats):
        X_train, X_test, Y_train, Y_test, A_train, A_test = train_test_split(X, 
                                                        Y, 
                                                        A,
                                                        test_size = 0.2,
                                                        random_state=131+i,
                                                        stratify=np.stack((Y, A), axis=1))
        X_train = X_train.reset_index(drop=True)
        X_test = X_test.reset_index(drop=True)
        clf = models[args.model]
        clf.fit(X_train, Y_train)
        Y_pred = clf.predict(X_test)

        report = responsibly.fairness.metrics.report_binary(Y_test, Y_pred, A_test)
        accuracy.append((Y_pred == Y_test).mean())
        dp.append(abs(report.loc['acceptance_rate'] - report.loc['acceptance_rate'].mean()).max())
        tpr = abs(report.loc['fnr'] - report.loc['fnr'].mean()).max()
        fpr = abs(report.loc['fpr'] - report.loc['fpr'].mean()).max()
        equal_tpr.append(tpr)
        equal_fpr.append(fpr)
        eo.append(max(tpr, fpr))

    reports = {
            'accuracy' : np.array(accuracy).mean(),
            'accuracy_std' : np.array(accuracy).std(),
            'DP' : np.array(dp).mean(),
            'DP_std' : np.array(dp).std(),
            'TPR' : np.array(tpr).mean(),
            'TPR_std' : np.array(tpr).std(),
            'FPR' : np.array(fpr).mean(),
            'FPR_std' : np.array(fpr).std(),
            'EO' : np.array(eo).mean(),
            'EO_std' : np.array(eo).std()
    }
    return reports

# compute mutual information between X and A
mis = []
for col in X.columns:
    mi = mutual_information_2d(X[col].values, A)
    mis.append((mi, col))
mis = sorted(mis, reverse=False)
mis1 = [l[1] for l in mis]

reports = {'accuracy':[], 'accuracy_std':[], 'DP':[], 'DP_std':[], 'TPR':[], 'TPR_std':[], 'FPR': [], 'FPR_std':[], 'EO': [], 'EO_std': []}
for i in range(args.n):
    Xt = X[mis1[:len(X.columns)-i]]
    report = run(Xt, Y, A, repeats=args.repeats)
    for k in reports.keys():
        reports[k].append(report[k])
    if i % 5 == 0:
        print(f'[INFO] Block {i} features.')
for k in reports.keys():
    reports[k] = np.array(reports[k])

# plot
palette = sns.color_palette()
fig, ax2 = plt.subplots()
idx = np.arange(args.n)
ax2.plot(idx, reports['DP'], color=palette[2], label='DP', marker='+')
ax2.fill_between(idx, reports['DP']-reports['DP_std'], reports['DP']+reports['DP_std'], color=palette[2], alpha=0.5)
# ax2.plot(idx, reports['TPR'], color=palette[3], label='TPR')
# ax2.plot(idx, reports['FPR'], color=palette[4], label='FPR')
ax2.plot(idx, reports['EO'], color=palette[5], label='EO')
ax2.fill_between(idx, reports['EO']-reports['EO_std'], reports['EO']+reports['EO_std'], color=palette[5], alpha=0.5)
ax2.set_ylabel('Disparity', color=palette[2], fontsize=20)
ax2.tick_params(axis='y', labelcolor=palette[2])
ax2.legend()
ax1 = ax2.twinx()
ax1.plot(idx, reports['accuracy'], color=palette[0], label='Accuracy')
ax1.fill_between(idx, reports['accuracy']-reports['accuracy_std'], reports['accuracy']+reports['accuracy_std'], color=palette[0], alpha=0.5)
ax1.set_xlabel('# of Blocked Features', fontsize=20)
ax1.set_ylabel('Accuracy', color=palette[0], fontsize=20)
ax1.tick_params(axis='y', labelcolor=palette[0])
ax1.set_title(f'{args.dataset} {args.model}', fontsize=24)
ax1.set_xlim(0, args.n)
ax1.grid(b=False)
plt.savefig(f'Figures/{args.dataset}_{args.model}_{args.n}.pdf')