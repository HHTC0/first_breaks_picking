import numpy as np
import torch
from matplotlib import pyplot as plt
from torch import cdist
from torch.optim import Adam
from tqdm import tqdm


def visualize_maps(x_vec, z_vec, model, x0, z0, device, max_vel=None):
    x_min, x_max = x_vec.min().item(), x_vec.max().item()
    z_min, z_max = z_vec.min().item(), z_vec.max().item()
    x_vec = x_vec.clone().float().to(device)
    z_vec = z_vec.clone().float().to(device)
    xx, zz = torch.meshgrid([x_vec, z_vec])
    xx = xx.flatten().view(-1, 1)
    zz = zz.flatten().view(-1, 1)

    source = torch.tensor([[x0, z0]], dtype=torch.float).repeat(len(xx), 1).to(device)
    receiver = torch.cat([xx, zz], dim=1)

    vel = model.get_velocity(source.clone().requires_grad_(True),
                             receiver.clone().requires_grad_(True)).detach().squeeze().cpu().numpy()

    vel_map = vel.reshape((len(x_vec), len(z_vec)), order='F')
    if max_vel:
        vel_map = np.clip(vel_map, 0, max_vel)

    time = model(source.clone().requires_grad_(True),
                 receiver.clone().requires_grad_(True)).detach().squeeze().cpu().numpy()

    time = time.reshape((len(x_vec), len(z_vec)), order='F')

    plt.imshow(vel_map, extent=[x_min, x_max, z_max, z_min])
    plt.colorbar()
    plt.show()

    plt.imshow(time, extent=[x_min, x_max, z_max, z_min])
    plt.colorbar()
    plt.show()

    return vel_map, time


def get_dataset(x_min, x_max, z_min, z_max, nx, nz, scalar_for_float=100000):
    x_vec = torch.linspace(x_min, x_max, nx)
    z_vec = torch.linspace(z_min, z_max, nz)

    xx, zz = torch.meshgrid([x_vec, z_vec])
    xx = xx.flatten().view(-1, 1)
    zz = zz.flatten().view(-1, 1)

    points = torch.cat([xx, zz], dim=1)

    distances = cdist(x1=points, x2=points, p=2) * scalar_for_float
    distances_norm = distances / distances.max()

    values_unique, counts = torch.unique(distances, return_counts=True, sorted=True)

    p = counts / sum(counts)
    w_unique = (1 - p) / (len(p) - 1)
    w_unique = w_unique / w_unique.max()

    mask_value2weight = distances.flatten() == values_unique.view(-1, 1)
    weights_counts = (mask_value2weight * w_unique.view(-1, 1)).sum(0)

    weights_dist = distances_norm.flatten()

    receiver = points.repeat(len(points), 1)
    source = points.repeat_interleave(len(points), dim=0)

    weights_res = weights_counts * weights_dist

    sr_pairs = torch.cartesian_prod(torch.arange(len(points)), torch.arange(len(points)))
    mask_to_keep = sr_pairs[:, 0] != sr_pairs[:, 1]

    return source[mask_to_keep], receiver[mask_to_keep], weights_res[mask_to_keep]


# _, _, weights = get_dataset(0, 1, 0, 1, 2, 3)
#
# print(len(weights))
#
# plt.hist(weights, bins=50)
# plt.show()


def train(model_arg, num_grid_arg, num_epochs_arg, lr_arg, title_arg, dim_arg, device):
    optim = Adam(lr=lr_arg, params=model_arg.parameters())
    loss_train_epochs = []
    loss_val_epochs = []

    s_train, r_train, weights_train = get_dataset(0.0, 1.0, 0.0, 1.0, num_grid_arg, num_grid_arg)
    s_val, r_val, _ = get_dataset(0.01, 0.99, 0.01, 0.99, num_grid_arg, num_grid_arg)

    s_train = s_train.to(device)
    r_train = r_train.to(device)
    weights_train = weights_train.to(device)

    s_val = s_val.to(device)
    r_val = r_val.to(device)

    # s_val = torch.rand((num_grid_arg, dim_arg), device=device)
    # r_val = torch.rand((num_grid_arg, dim_arg), device=device)

    pbar = tqdm(range(num_epochs_arg), desc=title_arg)

    for _ in pbar:
        model_arg.train()

        # s_train_inp = (torch.rand((num_grid_arg, dim_arg), device=device)).requires_grad_(True)
        # r_train_inp = (torch.rand((num_grid_arg, dim_arg), device=device)).requires_grad_(True)

        # print(s_train_inp.shape)

        s_train_inp = s_train.clone().requires_grad_(True)
        r_train_inp = r_train.clone().requires_grad_(True)
        # weights_train_inp = weights_train.clone()
        weights_train_inp = None

        loss = model_arg.loss(s_train_inp, r_train_inp, weights_train_inp)['loss']

        loss.backward()
        optim.step()

        if loss.isnan():
            raise ValueError('None!!!')

        loss_train = loss.item()

        optim.zero_grad()

        model_arg.eval()

        s_val_inp = s_val.clone().requires_grad_(True)
        r_val_inp = r_val.clone().requires_grad_(True)
        loss_val = model_arg.loss(s_val_inp, r_val_inp)

        loss_train_epochs.append(loss_train)
        loss_val['loss'] = loss_val['loss'].item()
        loss_val_epochs.append(loss_val['loss'])

        pbar.set_postfix({**loss_val,
                          'train': loss_train})

    plt.plot(loss_train_epochs, label='train')
    plt.plot(loss_val_epochs, label='val')
    plt.title(title_arg)
    plt.legend()
    plt.show()

    plt.plot(model_arg.logs_tau)
    plt.title('tau')
    plt.show()
    # plt.plot(model_arg.logs_t0)
    # plt.title('t0')
    # plt.show()
