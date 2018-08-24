# Bootstrap Cluster

Create a cluster with 3 nodes in the default pool, scale that default pool down
to 1 node (cheaper) and download the kubeconfig file.

NOTE: backup and delete `~/.kube/config` because `utils.py` is
minimum-viable-example library and not smart enough to parse kubeconf files
with multiple cluster definitions in it.

    gcloud container clusters create pcu --zone australia-southeast1-a
    gcloud container clusters resize pcu --node-pool default-pool --size=1 --zone australia-southeast1-a
    gcloud container clusters get-credentials pcu

# Deploy Demo Setup
Search for all occurrences of `CHANGEME` in all files and update the value to
match yours (most notably email and name of GCloud project):

    grep -R CHANGEME
    
Once you have updated all those value, deploy the manifest with

    kubectl apply -f deploy-webserver.py


# Terminate Load Balancers and Cluster

    kubectl delete -f deploy-webserver.py
    gcloud container clusters delete pcu
